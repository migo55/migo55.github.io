# Cardinal Lust — Multi-Angle Reel Pipeline

Turn a photographer's multi-angle room shots into **truthful** walkthrough
reels.

## The idea

Single-image → video models hallucinate geometry as the camera moves, because
they have to invent whatever is off-frame. Fine for a personal reel, unacceptable
for real estate.

The fix: photographers already shoot the same room from several angles. So we
use **real photos as the start and end frames** of keyframe interpolation. The
two endpoints are always truthful; the model only fills the short motion in
between. Chain several such hops (A→B→C→D) and you get a full room walkthrough
where every anchor is a real photograph.

The one failure mode — two frames too far apart in angle, so the invented
middle becomes fiction — is measured and flagged automatically.

## Pipeline

```
photos --group_by_room--> rooms
room   --order_room------> smooth start→end hops (+ safety flags)
        \--> plan.json + preview images --> [ you approve ] --.
hop    --provider--------> one clip (real start frame, real end frame)
clips  --stitch---------> one continuous room walkthrough
```

1. **grouping.py** — cluster the photo dump into rooms using capture time
   (EXIF) + perceptual hash. No manual tagging.
2. **ordering.py** — order each room's photos into the smoothest chain and
   score every hop's *viewpoint overlap* with ORB feature matching + RANSAC.
   Low overlap ⇒ the model would hallucinate ⇒ the hop is flagged **RISK**.
3. **providers/** — one interface (`VideoProvider`), swappable models:
   `mock` (offline crossfade, no API key), `kling`, `runway`, `luma` — all
   using native start-frame + end-frame keyframe conditioning.
4. **stitch.py** — ffmpeg-concat the hops into one walkthrough per room.

## Quick start

```bash
pip install -r requirements.txt         # needs ffmpeg on PATH too
```

### Review-first flow (recommended for the first runs)

Nothing renders until you approve the matchings the script guessed.

```bash
# 1. Propose room groupings + frame pairings. Writes plan.json AND a
#    side-by-side preview image of every pairing. No rendering yet.
python -m reel.cli plan ./photos --out ./out

# 2. Open ./out/previews/*.jpg to eyeball each start -> end pairing, then
#    approve. Either edit ./out/plan.json by hand (flip "approved": true/false),
#    or approve interactively (y/n per room and per hop):
python -m reel.cli approve --plan ./out/plan.json

# 3. Render ONLY what you approved (needs KLING_API_KEY / RUNWAY_API_KEY / …):
python -m reel.cli render --plan ./out/plan.json --provider kling --duration 5
```

In `plan.json`, `approved` defaults to the safety verdict — safe hops start
approved, RISK hops start rejected — so if you change nothing you still get the
truthful subset. Rejecting a whole room skips all its hops.

### One-shot flow (once you trust the matchings)

```bash
# Offline dry run — verifies the whole pipeline with a crossfade stand-in:
python -m reel.cli run ./photos --provider mock --out ./out

# Real render, dropping risky hops automatically:
python -m reel.cli run ./photos --provider kling --duration 5 --skip-risky
```

Flags:

- `--safe-overlap 0.12` — min viewpoint overlap for a hop to count as truthful.
  Raise it to be stricter about hallucination.
- `--skip-risky` — drop flagged hops instead of rendering them, so the final
  reel contains only truthful motion.

## Adding a video model

Implement one method:

```python
from reel.providers.base import VideoProvider, ClipRequest, ClipResult

class MyProvider(VideoProvider):
    name = "mine"
    def generate_clip(self, request: ClipRequest, out_path: str) -> ClipResult:
        # request.start_image and request.end_image are real photos on disk.
        # Render start→end interpolation to out_path, return ClipResult.
        ...
```

Then register it in `reel/providers/__init__.py`.

## Notes on the hosted adapters

`kling.py`, `runway.py`, `luma.py` track each vendor's public API at the time of
writing (async submit → poll → download). If a vendor revises field names or the
model id, that single adapter file is the only thing to update — the rest of the
pipeline is vendor-agnostic. Luma expects public image URLs; pass a `url_for`
callable if your frames are local.

## Where this goes next

For premium listings that need **zero** hallucination, the same multi-angle
photo sets are exactly the input for Gaussian Splatting / photogrammetry (Luma,
Polycam): reconstruct the real 3D room and fly a real camera through it. That
would slot in as another provider-like stage.
