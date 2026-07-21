"""Human-in-the-loop review: propose, approve, then render.

On the first runs you don't want the script to silently render whatever it
guessed. So the pipeline is split in two:

  1. build a PLAN  -> rooms + hops + overlap scores, written to plan.json,
     with a side-by-side preview image for every proposed pairing.
  2. you APPROVE   -> flip `approved` flags (interactively or by editing the
     JSON / deleting previews you don't like).
  3. RENDER        -> only approved rooms and hops are sent to the video model.

`approved` defaults to the safety verdict: safe hops start approved, RISK hops
start rejected, so doing nothing already gives you the truthful subset. You
override from there.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field

from PIL import Image, ImageDraw

from .grouping import group_by_room, load_photos
from .ordering import order_room

PLAN_VERSION = 1


@dataclass
class HopPlan:
    index: int
    start: str          # photo path
    end: str            # photo path
    overlap: float
    safe: bool
    approved: bool
    preview: str = ""   # path to the side-by-side review image


@dataclass
class RoomPlan:
    label: str
    approved: bool
    photos: list[str]
    hops: list[HopPlan] = field(default_factory=list)


@dataclass
class Plan:
    version: int
    safe_overlap: float
    rooms: list[RoomPlan] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    @staticmethod
    def from_dict(d: dict) -> "Plan":
        rooms = [
            RoomPlan(
                label=r["label"],
                approved=r["approved"],
                photos=r["photos"],
                hops=[HopPlan(**h) for h in r["hops"]],
            )
            for r in d["rooms"]
        ]
        return Plan(version=d["version"], safe_overlap=d["safe_overlap"], rooms=rooms)


def build_plan(photo_paths: list[str], safe_overlap: float = 0.12) -> Plan:
    """Group + order without rendering anything."""
    photos = load_photos(photo_paths)
    rooms = group_by_room(photos)

    plan = Plan(version=PLAN_VERSION, safe_overlap=safe_overlap)
    for room in rooms:
        ordered = order_room(room, safe_overlap=safe_overlap)
        hops = [
            HopPlan(
                index=i,
                start=h.start.path,
                end=h.end.path,
                overlap=round(h.overlap, 4),
                safe=h.safe,
                approved=h.safe,  # default: approve safe hops, reject risky ones
            )
            for i, h in enumerate(ordered.hops)
        ]
        plan.rooms.append(
            RoomPlan(
                label=room.label,
                approved=len(hops) > 0,  # single-frame rooms can't animate
                photos=[p.path for p in room.photos],
                hops=hops,
            )
        )
    return plan


def _side_by_side(start: str, end: str, caption: str, out_path: str) -> None:
    """Write a start|end review image with a caption bar."""
    h = 360
    imgs = []
    for p in (start, end):
        im = Image.open(p).convert("RGB")
        w = int(im.width * h / im.height)
        imgs.append(im.resize((w, h), Image.LANCZOS))
    gap, bar = 8, 34
    total_w = imgs[0].width + gap + imgs[1].width
    canvas = Image.new("RGB", (total_w, h + bar), (18, 18, 18))
    canvas.paste(imgs[0], (0, bar))
    canvas.paste(imgs[1], (imgs[0].width + gap, bar))
    ImageDraw.Draw(canvas).text((8, 9), caption, fill=(255, 255, 255))
    canvas.save(out_path)


def write_previews(plan: Plan, out_dir: str) -> None:
    """Render a review image per hop so pairings can be eyeballed."""
    prev_dir = os.path.join(out_dir, "previews")
    os.makedirs(prev_dir, exist_ok=True)
    for room in plan.rooms:
        for hop in room.hops:
            flag = "OK" if hop.safe else "RISK"
            caption = (
                f"{room.label} hop {hop.index}  [{flag}]  overlap={hop.overlap:.2f}   "
                f"{os.path.basename(hop.start)}  ->  {os.path.basename(hop.end)}"
            )
            out = os.path.join(prev_dir, f"{room.label}_hop{hop.index:02d}.jpg")
            _side_by_side(hop.start, hop.end, caption, out)
            hop.preview = out


def save_plan(plan: Plan, path: str) -> None:
    with open(path, "w") as fh:
        fh.write(plan.to_json())


def load_plan(path: str) -> Plan:
    with open(path) as fh:
        return Plan.from_dict(json.load(fh))


def interactive_approve(plan: Plan, ask=input, out=print) -> Plan:
    """Walk the operator through each room and hop, y/n per item.

    Pressing Enter keeps the current default (the safety verdict). Rejecting a
    room skips all its hops.
    """
    def yn(prompt: str, default: bool) -> bool:
        hint = "Y/n" if default else "y/N"
        ans = ask(f"{prompt} [{hint}] ").strip().lower()
        if not ans:
            return default
        return ans.startswith("y")

    for room in plan.rooms:
        n = len(room.hops)
        if n == 0:
            out(f"\n{room.label}: only one frame, cannot animate -- skipped.")
            room.approved = False
            continue
        out(f"\n=== {room.label} ({len(room.photos)} photos, {n} hop(s)) ===")
        room.approved = yn(f"Keep {room.label} as one room?", room.approved)
        if not room.approved:
            for hop in room.hops:
                hop.approved = False
            continue
        for hop in room.hops:
            flag = "OK" if hop.safe else "RISK"
            out(
                f"  hop {hop.index}: [{flag}] overlap={hop.overlap:.2f}  "
                f"{os.path.basename(hop.start)} -> {os.path.basename(hop.end)}"
            )
            if hop.preview:
                out(f"    preview: {hop.preview}")
            hop.approved = yn(f"  Render hop {hop.index}?", hop.approved)
    return plan


def approved_hops(plan: Plan):
    """Yield (room, hop) pairs that survived approval, for rendering."""
    for room in plan.rooms:
        if not room.approved:
            continue
        for hop in room.hops:
            if hop.approved:
                yield room, hop
