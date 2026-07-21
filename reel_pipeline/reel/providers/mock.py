"""A real, offline provider that needs no API key.

It renders an actual clip by cross-dissolving the start frame into the end
frame with ffmpeg. This is NOT keyframe interpolation -- there is no learned
motion -- but it produces a valid video for every hop so you can test the whole
pipeline (grouping -> ordering -> render -> stitch) end to end without spending
a cent or waiting on a hosted model.

Swap this for KlingProvider / RunwayProvider / LumaProvider when you are ready
to render for real.
"""

from __future__ import annotations

import shutil
import subprocess

from .base import ClipRequest, ClipResult, VideoProvider


class MockProvider(VideoProvider):
    name = "mock"

    def __init__(self) -> None:
        if shutil.which("ffmpeg") is None:
            raise RuntimeError("MockProvider needs ffmpeg on PATH.")

    def generate_clip(self, request: ClipRequest, out_path: str) -> ClipResult:
        dur = request.duration_s
        fps = request.fps
        # Two still inputs; xfade over the full duration -> a crossfade clip.
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-t", f"{dur}", "-i", request.start_image,
            "-loop", "1", "-t", f"{dur}", "-i", request.end_image,
            "-filter_complex",
            (
                f"[0:v]scale=1280:720:force_original_aspect_ratio=decrease,"
                f"pad=1280:720:-1:-1,setsar=1[a];"
                f"[1:v]scale=1280:720:force_original_aspect_ratio=decrease,"
                f"pad=1280:720:-1:-1,setsar=1[b];"
                f"[a][b]xfade=transition=fade:duration={dur}:offset=0,"
                f"fps={fps}[v]"
            ),
            "-map", "[v]", "-pix_fmt", "yuv420p", out_path,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg failed:\n{proc.stderr[-800:]}")
        return ClipResult(output_path=out_path, provider=self.name)

    def supports_keyframes(self) -> bool:
        # It uses both frames, but as a dumb crossfade, not real interpolation.
        return True
