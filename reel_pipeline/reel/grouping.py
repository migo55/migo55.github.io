"""Group a photographer's photo dump into per-room clusters.

Photographers usually shoot the same room from several angles, then move on
to the next room. Two signals let us recover those groups without any manual
tagging:

  1. Capture time (EXIF DateTimeOriginal): shots of one room are bunched
     together in time.
  2. Visual similarity (perceptual hash): angles of the same room share a lot
     of coarse structure, so their hashes are close in Hamming distance.

We combine both: a new photo joins the current room while it stays visually
close to the room's anchor OR was taken within a short time gap; otherwise it
starts a new room. This is deliberately simple and dependency-light so it is
easy to tune per photographer.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from PIL import Image, ExifTags

# EXIF tag id for DateTimeOriginal, resolved once.
_DATETIME_ORIGINAL = next(
    (k for k, v in ExifTags.TAGS.items() if v == "DateTimeOriginal"), 36867
)


@dataclass
class Photo:
    """A single input photo plus the features we derive from it."""

    path: str
    dhash: int = 0
    taken_at: Optional[datetime] = None

    @property
    def name(self) -> str:
        return os.path.basename(self.path)


@dataclass
class Room:
    """A cluster of photos believed to be the same room."""

    index: int
    photos: list[Photo] = field(default_factory=list)

    @property
    def label(self) -> str:
        return f"room_{self.index:02d}"


def _dhash(path: str, size: int = 8) -> int:
    """Difference hash: robust to lighting/scale, sensitive to structure."""
    img = Image.open(path).convert("L").resize((size + 1, size), Image.LANCZOS)
    px = list(img.getdata())
    bits = 0
    for row in range(size):
        for col in range(size):
            left = px[row * (size + 1) + col]
            right = px[row * (size + 1) + col + 1]
            bits = (bits << 1) | (1 if left > right else 0)
    return bits


def _taken_at(path: str) -> Optional[datetime]:
    try:
        exif = Image.open(path).getexif()
        raw = exif.get(_DATETIME_ORIGINAL)
        if raw:
            return datetime.strptime(raw, "%Y:%m:%d %H:%M:%S")
    except Exception:
        pass
    return None


def _hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def load_photos(paths: list[str]) -> list[Photo]:
    """Read each file once and precompute the features grouping needs."""
    photos = [
        Photo(path=p, dhash=_dhash(p), taken_at=_taken_at(p)) for p in paths
    ]
    # Order by capture time when available so the time-gap heuristic is valid;
    # fall back to filename order (photographers usually export sequentially).
    photos.sort(key=lambda ph: (ph.taken_at or datetime.min, ph.name))
    return photos


def group_by_room(
    photos: list[Photo],
    hash_threshold: int = 22,
    time_gap_seconds: float = 90.0,
) -> list[Room]:
    """Cluster photos into rooms.

    hash_threshold  : max Hamming distance (out of 64) to still count as the
                      same room by appearance. Higher = more lenient.
    time_gap_seconds: shots within this gap are kept together even if a wide
                      angle change pushed the hash apart.
    """
    rooms: list[Room] = []
    current: Optional[Room] = None
    anchor: Optional[Photo] = None

    for photo in photos:
        if current is None:
            current = Room(index=0)
            rooms.append(current)
            anchor = photo
            current.photos.append(photo)
            continue

        close_visually = _hamming(photo.dhash, anchor.dhash) <= hash_threshold
        close_in_time = (
            anchor.taken_at is not None
            and photo.taken_at is not None
            and abs((photo.taken_at - anchor.taken_at).total_seconds())
            <= time_gap_seconds
        )

        if close_visually or close_in_time:
            current.photos.append(photo)
            # Slide the anchor forward so a slow pan around the room keeps
            # chaining instead of snapping back to the first shot.
            anchor = photo
        else:
            current = Room(index=len(rooms))
            rooms.append(current)
            anchor = photo
            current.photos.append(photo)

    return rooms
