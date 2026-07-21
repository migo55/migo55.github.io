"""Luma Dream Machine adapter -- keyframes at frame0 and frame1.

Luma expresses start/end frames as `keyframes`: `frame0` is the start image,
`frame1` is the end image. Same contract, same async submit -> poll ->
download shape. Set LUMA_API_KEY.

Luma wants publicly reachable image URLs rather than base64. If your frames are
local, host them first (e.g. a signed S3/GCS URL) and pass a `url_for`
callable that maps a local path to its public URL.
"""

from __future__ import annotations

import os
import time
from typing import Callable

import requests

from .base import ClipRequest, ClipResult, VideoProvider

_BASE = os.environ.get("LUMA_BASE_URL", "https://api.lumalabs.ai/dream-machine/v1")
_POLL_TIMEOUT_S = 600
_POLL_INTERVAL_S = 6


class LumaProvider(VideoProvider):
    name = "luma"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "ray-2",
        url_for: Callable[[str], str] | None = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("LUMA_API_KEY")
        if not self.api_key:
            raise RuntimeError("Set LUMA_API_KEY or pass api_key=.")
        self.model = model
        # Luma needs public URLs; default assumes the paths are already URLs.
        self.url_for = url_for or (lambda p: p)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def generate_clip(self, request: ClipRequest, out_path: str) -> ClipResult:
        payload = {
            "model": self.model,
            "prompt": request.prompt,
            "keyframes": {
                "frame0": {"type": "image", "url": self.url_for(request.start_image)},
                "frame1": {"type": "image", "url": self.url_for(request.end_image)},
            },
        }
        submit = requests.post(
            f"{_BASE}/generations", json=payload, headers=self._headers(), timeout=60
        )
        submit.raise_for_status()
        gen_id = submit.json()["id"]

        video_url = self._poll(gen_id)
        self._download(video_url, out_path)
        return ClipResult(output_path=out_path, provider=self.name, raw={"id": gen_id})

    def _poll(self, gen_id: str) -> str:
        deadline = time.monotonic() + _POLL_TIMEOUT_S
        url = f"{_BASE}/generations/{gen_id}"
        while time.monotonic() < deadline:
            resp = requests.get(url, headers=self._headers(), timeout=30)
            resp.raise_for_status()
            data = resp.json()
            state = data.get("state")
            if state == "completed":
                return data["assets"]["video"]
            if state == "failed":
                raise RuntimeError(f"Luma generation {gen_id} failed: {data.get('failure_reason')}")
            time.sleep(_POLL_INTERVAL_S)
        raise TimeoutError(f"Luma generation {gen_id} did not finish in {_POLL_TIMEOUT_S}s.")

    @staticmethod
    def _download(url: str, out_path: str) -> None:
        with requests.get(url, stream=True, timeout=120) as r:
            r.raise_for_status()
            with open(out_path, "wb") as fh:
                for chunk in r.iter_content(chunk_size=1 << 16):
                    fh.write(chunk)
