"""Command-line entrypoint.

    python -m reel.cli ./photos --provider mock --out ./out
    python -m reel.cli ./photos --provider kling --duration 5 --skip-risky
"""

from __future__ import annotations

import argparse
import glob
import os
import sys

from .pipeline import run
from .providers import get_provider

_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff")


def _collect(inputs: list[str]) -> list[str]:
    paths: list[str] = []
    for item in inputs:
        if os.path.isdir(item):
            for ext in _IMAGE_EXTS:
                paths += glob.glob(os.path.join(item, f"*{ext}"))
                paths += glob.glob(os.path.join(item, f"*{ext.upper()}"))
        else:
            paths.append(item)
    return sorted(set(paths))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Cardinal Lust multi-angle reel pipeline.")
    ap.add_argument("inputs", nargs="+", help="Photo files or a folder of photos.")
    ap.add_argument("--provider", default="mock", help="mock | kling | runway | luma")
    ap.add_argument("--out", default="./out", help="Output directory.")
    ap.add_argument("--duration", type=float, default=3.0, help="Seconds per hop.")
    ap.add_argument(
        "--safe-overlap",
        type=float,
        default=0.12,
        help="Min viewpoint overlap for a hop to count as truthful (0..1).",
    )
    ap.add_argument(
        "--skip-risky",
        action="store_true",
        help="Drop hops below the overlap threshold instead of rendering them.",
    )
    args = ap.parse_args(argv)

    paths = _collect(args.inputs)
    if len(paths) < 2:
        print("Need at least 2 photos.", file=sys.stderr)
        return 2

    provider = get_provider(args.provider)
    result = run(
        photo_paths=paths,
        provider=provider,
        out_dir=args.out,
        duration_s=args.duration,
        safe_overlap=args.safe_overlap,
        skip_risky=args.skip_risky,
        on_event=print,
    )

    print("\n=== Summary ===")
    for room in result.rooms:
        status = room.walkthrough_path or "(no walkthrough)"
        print(f"{room.room_label}: {status}")
        for risk in room.risky_hops:
            print(f"    risky: {risk}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
