"""Offline smoke test: generate synthetic room photos and run the pipeline.

Creates two fake "rooms" (each a few slightly panned angles), then runs the
full grouping -> ordering -> mock render -> stitch pipeline. Verifies the
plumbing without any API key. Requires ffmpeg for the mock provider/stitch.

    python examples/smoke_test.py
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from reel.grouping import group_by_room, load_photos  # noqa: E402
from reel.ordering import order_room  # noqa: E402


def _make_room(dir_: str, prefix: str, base_hue: int, shift: int) -> None:
    """A few frames of one 'room': same scene, panned a little each shot."""
    for i in range(3):
        img = Image.new("RGB", (640, 480), (base_hue, 40, 60))
        d = ImageDraw.Draw(img)
        # A few 'furniture' rectangles that slide as the camera pans -> gives
        # ORB something structural to match across frames.
        for k in range(5):
            x = 60 + k * 110 - i * shift
            d.rectangle([x, 120 + k * 10, x + 80, 320], fill=(200, 180 - k * 20, 90))
        d.text((20, 20), f"{prefix} angle {i}", fill=(255, 255, 255))
        img.save(os.path.join(dir_, f"{prefix}_{i}.png"))


def main() -> int:
    if shutil.which("ffmpeg") is None:
        print("SKIP: ffmpeg not on PATH (ordering/grouping still testable).")

    work = tempfile.mkdtemp(prefix="reel_smoke_")
    photos_dir = os.path.join(work, "photos")
    os.makedirs(photos_dir)
    _make_room(photos_dir, "living", base_hue=40, shift=25)
    _make_room(photos_dir, "kitchen", base_hue=90, shift=25)

    paths = sorted(
        os.path.join(photos_dir, f) for f in os.listdir(photos_dir)
    )
    photos = load_photos(paths)
    rooms = group_by_room(photos)
    print(f"Grouped {len(photos)} photos into {len(rooms)} room(s).")

    for room in rooms:
        ordered = order_room(room)
        print(f"  {room.label}: {len(room.photos)} photos, {len(ordered.hops)} hop(s)")
        for h in ordered.hops:
            flag = "OK" if h.safe else "RISK"
            print(f"    {flag} overlap={h.overlap:.2f}  {h.start.name} -> {h.end.name}")

    assert len(rooms) >= 1, "expected at least one room"
    print("\nOrdering + grouping OK.")

    # Full render only if ffmpeg is present.
    if shutil.which("ffmpeg") is not None:
        from reel.pipeline import run
        from reel.providers import get_provider

        out = os.path.join(work, "out")
        result = run(paths, get_provider("mock"), out, duration_s=1.0, on_event=print)
        made = [r.walkthrough_path for r in result.rooms if r.walkthrough_path]
        assert made, "expected at least one walkthrough video"
        for p in made:
            assert os.path.getsize(p) > 0, f"empty video: {p}"
        print(f"\nRendered {len(made)} walkthrough(s). Full pipeline OK.")

    print(f"\nArtifacts in: {work}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
