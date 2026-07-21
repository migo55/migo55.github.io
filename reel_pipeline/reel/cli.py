"""Command-line entrypoint.

Human-in-the-loop flow (recommended for the first runs):

    # 1. Propose groupings + pairings, write plan.json + preview images.
    python -m reel.cli plan ./photos --out ./out

    # 2. Review: open ./out/previews/*.jpg, then approve.
    #    Either edit ./out/plan.json by hand (flip "approved": true/false),
    #    or approve interactively:
    python -m reel.cli approve --plan ./out/plan.json

    # 3. Render only what you approved.
    python -m reel.cli render --plan ./out/plan.json --provider kling --out ./out

One-shot flow (once you trust the matchings):

    python -m reel.cli run ./photos --provider kling --skip-risky --out ./out
"""

from __future__ import annotations

import argparse
import glob
import os
import sys

from .pipeline import render_plan, run
from .plan import build_plan, interactive_approve, load_plan, save_plan, write_previews
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


def _cmd_plan(args) -> int:
    paths = _collect(args.inputs)
    if len(paths) < 2:
        print("Need at least 2 photos.", file=sys.stderr)
        return 2
    os.makedirs(args.out, exist_ok=True)
    plan = build_plan(paths, safe_overlap=args.safe_overlap)
    write_previews(plan, args.out)
    plan_path = os.path.join(args.out, "plan.json")
    save_plan(plan, plan_path)

    n_rooms = len(plan.rooms)
    n_hops = sum(len(r.hops) for r in plan.rooms)
    n_risky = sum(1 for r in plan.rooms for h in r.hops if not h.safe)
    print(f"Proposed {n_rooms} room(s), {n_hops} hop(s), {n_risky} flagged RISK.")
    print(f"Plan:     {plan_path}")
    print(f"Previews: {os.path.join(args.out, 'previews')}/  (open these to eyeball pairings)")
    print("\nNext: review, then")
    print(f"  python -m reel.cli approve --plan {plan_path}")
    print(f"  python -m reel.cli render  --plan {plan_path} --provider <name>")
    return 0


def _cmd_approve(args) -> int:
    plan = load_plan(args.plan)
    interactive_approve(plan)
    save_plan(plan, args.plan)
    approved = sum(1 for r in plan.rooms if r.approved for h in r.hops if h.approved)
    print(f"\nSaved. {approved} hop(s) approved for rendering -> {args.plan}")
    return 0


def _cmd_render(args) -> int:
    plan = load_plan(args.plan)
    provider = get_provider(args.provider)
    out_dir = args.out or os.path.dirname(os.path.abspath(args.plan))
    result = render_plan(
        plan, provider, out_dir, duration_s=args.duration, on_event=print
    )
    print("\n=== Summary ===")
    for room in result.rooms:
        print(f"{room.room_label}: {room.walkthrough_path or '(no walkthrough)'}")
    return 0


def _cmd_run(args) -> int:
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
        print(f"{room.room_label}: {room.walkthrough_path or '(no walkthrough)'}")
        for risk in room.risky_hops:
            print(f"    risky: {risk}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Cardinal Lust multi-angle reel pipeline.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("plan", help="Propose groupings + pairings, write plan.json + previews.")
    p.add_argument("inputs", nargs="+", help="Photo files or a folder of photos.")
    p.add_argument("--out", default="./out")
    p.add_argument("--safe-overlap", type=float, default=0.12)
    p.set_defaults(func=_cmd_plan)

    a = sub.add_parser("approve", help="Interactively approve a plan (y/n per room and hop).")
    a.add_argument("--plan", required=True)
    a.set_defaults(func=_cmd_approve)

    r = sub.add_parser("render", help="Render only the approved rooms/hops from a plan.")
    r.add_argument("--plan", required=True)
    r.add_argument("--provider", default="mock", help="mock | kling | runway | luma")
    r.add_argument("--out", default=None, help="Defaults to the plan's folder.")
    r.add_argument("--duration", type=float, default=3.0)
    r.set_defaults(func=_cmd_render)

    o = sub.add_parser("run", help="One-shot: group, order, render, stitch (no approval step).")
    o.add_argument("inputs", nargs="+")
    o.add_argument("--provider", default="mock")
    o.add_argument("--out", default="./out")
    o.add_argument("--duration", type=float, default=3.0)
    o.add_argument("--safe-overlap", type=float, default=0.12)
    o.add_argument("--skip-risky", action="store_true")
    o.set_defaults(func=_cmd_run)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
