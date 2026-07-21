"""Order the frames within a room and guard against big angular jumps.

This is the heart of the "precise, not hallucinated" idea.

Keyframe interpolation (start frame + end frame) is truthful at the two
endpoints because those are real photos. The model only invents the motion in
between. That invented middle stays plausible ONLY when the two frames share
enough of the same scene -- i.e. the camera moved a little, not a lot.

We measure "how much two frames overlap" with ORB feature matching: detect
keypoints in both images, match them, and fit a homography with RANSAC. The
fraction of matches that survive as geometric inliers is a good proxy for
viewpoint overlap:

    overlap ~ 1.0  -> nearly the same shot, safe to interpolate
    overlap ~ 0.0  -> different views, the model would hallucinate the gap

From that pairwise overlap we do two things:
  1. Order the room's photos into a smooth chain (greedy nearest-neighbour on
     a "most overlap first" basis), so consecutive hops are as small as
     possible.
  2. Flag any consecutive pair whose overlap is below a safety threshold, so
     the studio can drop in an intermediate angle instead of shipping a
     hallucinated segment.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from .grouping import Photo, Room


@dataclass
class Hop:
    """One start->end segment that will become a single interpolated clip."""

    start: Photo
    end: Photo
    overlap: float          # 0..1, higher = safer
    safe: bool              # overlap >= threshold


@dataclass
class OrderedRoom:
    room: Room
    hops: list[Hop]

    @property
    def has_risky_hops(self) -> bool:
        return any(not h.safe for h in self.hops)


def _orb_overlap(path_a: str, path_b: str, max_features: int = 1500) -> float:
    """Return an overlap score in [0, 1] between two images."""
    img_a = cv2.imread(path_a, cv2.IMREAD_GRAYSCALE)
    img_b = cv2.imread(path_b, cv2.IMREAD_GRAYSCALE)
    if img_a is None or img_b is None:
        return 0.0

    orb = cv2.ORB_create(nfeatures=max_features)
    kp_a, des_a = orb.detectAndCompute(img_a, None)
    kp_b, des_b = orb.detectAndCompute(img_b, None)
    if des_a is None or des_b is None or len(kp_a) < 8 or len(kp_b) < 8:
        return 0.0

    matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
    raw = matcher.knnMatch(des_a, des_b, k=2)
    # Lowe's ratio test keeps only confident, distinctive matches.
    good = [m for m, n in (p for p in raw if len(p) == 2) if m.distance < 0.75 * n.distance]
    if len(good) < 8:
        return 0.0

    src = np.float32([kp_a[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst = np.float32([kp_b[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    _, mask = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)
    if mask is None:
        return 0.0

    inliers = int(mask.sum())
    # Normalise by the smaller keypoint set so the score is a true fraction.
    denom = max(1, min(len(kp_a), len(kp_b)))
    return min(1.0, inliers / denom)


def _overlap_matrix(photos: list[Photo]) -> np.ndarray:
    n = len(photos)
    m = np.zeros((n, n), dtype=np.float32)
    for i in range(n):
        for j in range(i + 1, n):
            score = _orb_overlap(photos[i].path, photos[j].path)
            m[i, j] = m[j, i] = score
    return m


def order_room(
    room: Room,
    safe_overlap: float = 0.12,
    overlap_fn=None,
) -> OrderedRoom:
    """Chain a room's photos into smooth start->end hops.

    safe_overlap: minimum inlier fraction for a hop to be considered truthful.
                  Tune per photographer; 0.12 is a sane starting point for
                  interior real-estate shots.
    overlap_fn  : injectable scorer (photos, i, j) -> float, mainly for tests.
    """
    photos = room.photos
    if len(photos) < 2:
        return OrderedRoom(room=room, hops=[])

    matrix = (
        _overlap_matrix(photos)
        if overlap_fn is None
        else np.array(
            [[overlap_fn(photos, i, j) for j in range(len(photos))]
             for i in range(len(photos))],
            dtype=np.float32,
        )
    )

    # Greedy nearest-neighbour tour: start from the photo with the highest
    # single overlap (most "central" shot) and always step to the most
    # overlapping unvisited frame. Keeps each hop as small as possible.
    n = len(photos)
    start_idx = int(np.unravel_index(np.argmax(matrix), matrix.shape)[0])
    order = [start_idx]
    visited = {start_idx}
    while len(order) < n:
        last = order[-1]
        candidates = [(matrix[last, j], j) for j in range(n) if j not in visited]
        _, nxt = max(candidates)
        order.append(nxt)
        visited.add(nxt)

    hops: list[Hop] = []
    for a, b in zip(order, order[1:]):
        score = float(matrix[a, b])
        hops.append(
            Hop(
                start=photos[a],
                end=photos[b],
                overlap=score,
                safe=score >= safe_overlap,
            )
        )
    return OrderedRoom(room=room, hops=hops)
