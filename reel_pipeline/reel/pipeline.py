"""End-to-end orchestration: photo dump -> per-room walkthrough reels.

    photos  --group_by_room-->  rooms
    room    --order_room-------> smooth start->end hops (+ safety flags)
    hop     --provider---------> one truthful-endpoints clip
    clips   --stitch----------->  one continuous room walkthrough

The safety flags from ordering are surfaced, not hidden: risky hops (two frames
too far apart in angle) are reported so the studio can insert an intermediate
photo instead of shipping a hallucinated segment.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from .grouping import group_by_room, load_photos
from .ordering import OrderedRoom, order_room
from .plan import Plan, approved_hops
from .providers import ClipRequest, VideoProvider


@dataclass
class RoomResult:
    room_label: str
    walkthrough_path: str | None
    clip_paths: list[str] = field(default_factory=list)
    risky_hops: list[str] = field(default_factory=list)


@dataclass
class PipelineResult:
    rooms: list[RoomResult] = field(default_factory=list)

    @property
    def any_risky(self) -> bool:
        return any(r.risky_hops for r in self.rooms)


def run(
    photo_paths: list[str],
    provider: VideoProvider,
    out_dir: str,
    duration_s: float = 3.0,
    safe_overlap: float = 0.12,
    skip_risky: bool = False,
    on_event=lambda msg: None,
) -> PipelineResult:
    """Run the full pipeline.

    skip_risky: if True, drop hops below the overlap threshold instead of
                rendering them -- so the final reel contains only truthful
                motion. If False, they are still rendered but reported.
    on_event  : optional progress callback (e.g. print) for CLI/logging.
    """
    from .stitch import stitch

    os.makedirs(out_dir, exist_ok=True)

    on_event("Loading photos and extracting features...")
    photos = load_photos(photo_paths)

    on_event("Grouping photos into rooms...")
    rooms = group_by_room(photos)
    on_event(f"Found {len(rooms)} room(s) across {len(photos)} photo(s).")

    result = PipelineResult()

    for room in rooms:
        on_event(f"\n[{room.label}] {len(room.photos)} photo(s)")
        ordered: OrderedRoom = order_room(room, safe_overlap=safe_overlap)

        if not ordered.hops:
            on_event(f"[{room.label}] only one usable frame; skipping (need >=2).")
            result.rooms.append(RoomResult(room_label=room.label, walkthrough_path=None))
            continue

        clip_paths: list[str] = []
        risky: list[str] = []

        for i, hop in enumerate(ordered.hops):
            tag = f"{hop.start.name} -> {hop.end.name}"
            flag = "OK " if hop.safe else "RISK"
            on_event(f"[{room.label}] hop {i}: {flag} overlap={hop.overlap:.2f}  {tag}")

            if not hop.safe:
                risky.append(f"{tag} (overlap={hop.overlap:.2f})")
                if skip_risky:
                    on_event(f"[{room.label}] hop {i}: skipped (below safe overlap).")
                    continue

            clip_path = os.path.join(out_dir, f"{room.label}_hop{i:02d}.mp4")
            req = ClipRequest(
                start_image=hop.start.path,
                end_image=hop.end.path,
                duration_s=duration_s,
            )
            provider.generate_clip(req, clip_path)
            clip_paths.append(clip_path)

        walkthrough = None
        if clip_paths:
            walkthrough = os.path.join(out_dir, f"{room.label}_walkthrough.mp4")
            stitch(clip_paths, walkthrough)
            on_event(f"[{room.label}] walkthrough -> {walkthrough}")

        result.rooms.append(
            RoomResult(
                room_label=room.label,
                walkthrough_path=walkthrough,
                clip_paths=clip_paths,
                risky_hops=risky,
            )
        )

    if result.any_risky:
        on_event(
            "\nHeads up: some hops had low viewpoint overlap. Consider adding an "
            "intermediate angle between those frames for a truthful in-between."
        )
    return result


def render_plan(
    plan: Plan,
    provider: VideoProvider,
    out_dir: str,
    duration_s: float = 3.0,
    on_event=lambda msg: None,
) -> PipelineResult:
    """Render only the rooms/hops an operator approved in a reviewed plan.

    This is the second half of the human-in-the-loop flow: `build_plan` +
    approval decide *what* to render, this decides *how* and stitches it.
    """
    from .stitch import stitch

    os.makedirs(out_dir, exist_ok=True)
    result = PipelineResult()

    # Group approved hops back under their room so we stitch per room.
    per_room: dict[str, list] = {}
    for room, hop in approved_hops(plan):
        per_room.setdefault(room.label, []).append(hop)

    if not per_room:
        on_event("Nothing approved in this plan -- nothing to render.")
        return result

    for label, hops in per_room.items():
        clip_paths: list[str] = []
        for hop in hops:
            on_event(
                f"[{label}] rendering hop {hop.index}: "
                f"{os.path.basename(hop.start)} -> {os.path.basename(hop.end)}"
            )
            clip_path = os.path.join(out_dir, f"{label}_hop{hop.index:02d}.mp4")
            req = ClipRequest(start_image=hop.start, end_image=hop.end, duration_s=duration_s)
            provider.generate_clip(req, clip_path)
            clip_paths.append(clip_path)

        walkthrough = None
        if clip_paths:
            walkthrough = os.path.join(out_dir, f"{label}_walkthrough.mp4")
            stitch(clip_paths, walkthrough)
            on_event(f"[{label}] walkthrough -> {walkthrough}")

        result.rooms.append(
            RoomResult(room_label=label, walkthrough_path=walkthrough, clip_paths=clip_paths)
        )
    return result
