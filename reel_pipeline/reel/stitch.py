"""Concatenate per-hop clips into one continuous walkthrough with ffmpeg."""

from __future__ import annotations

import os
import shutil
import subprocess


def stitch(clip_paths: list[str], out_path: str, reencode: bool = True) -> str:
    """Join clips in order into a single video.

    reencode=True is the safe default: hops rendered by different providers (or
    the mock) can differ in codec/fps, and concat demuxer copy mode fails on
    mismatches. Re-encoding normalises them.
    """
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("stitch needs ffmpeg on PATH.")
    if not clip_paths:
        raise ValueError("No clips to stitch.")

    list_file = out_path + ".concat.txt"
    with open(list_file, "w") as fh:
        for path in clip_paths:
            fh.write(f"file '{os.path.abspath(path)}'\n")

    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file]
    if reencode:
        cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "24"]
    else:
        cmd += ["-c", "copy"]
    cmd += [out_path]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    os.remove(list_file)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg concat failed:\n{proc.stderr[-800:]}")
    return out_path
