"""Kling adapter -- native start-frame + end-frame keyframe interpolation.

Kling's image-to-video endpoint accepts both an `image` (start frame) and an
`image_tail` (end frame). That is exactly our contract: two real photos in, one
truthful-endpoints clip out.

This is written against Kling's async job pattern (submit -> poll -> download).
Field names track the public API at time of writing; if Kling revises them,
this one file is the only thing you touch. Set KLING_API_KEY in the environment.

Images are sent as base64 so you do not need a public URL for local files.
"""

from __future__ import annotations

import base64
import os
import time

import requests

from .base import ClipRequest, ClipResult, VideoProvider

_BASE = os.environ.get("KLING_BASE_URL", "https://api.klingai.com")
_SUBMIT = "/v1/videos/image2video"
_POLL_TIMEOUT_S = 600
_POLL_INTERVAL_S = 6


def _b64(path: str) -> str:
    with open(path, "rb") as fh:
        return base64.b64encode(fh.read()).decode("ascii")


class KlingProvider(VideoProvider):
    name = "kling"

    def __init__(self, api_key: str | None = None, model: str = "kling-v1-6") -> None:
        self.api_key = api_key or os.environ.get("KLING_API_KEY")
        if not self.api_key:
            raise RuntimeError("Set KLING_API_KEY or pass api_key=.")
        self.model = model

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def generate_clip(self, request: ClipRequest, out_path: str) -> ClipResult:
        payload = {
            "model_name": self.model,
            "image": _b64(request.start_image),        # start frame
            "image_tail": _b64(request.end_image),     # end frame
            "prompt": request.prompt,
            "duration": str(int(round(request.duration_s))),
            "mode": "std",
        }
        submit = requests.post(
            f"{_BASE}{_SUBMIT}", json=payload, headers=self._headers(), timeout=60
        )
        submit.raise_for_status()
        task_id = submit.json()["data"]["task_id"]

        video_url = self._poll(task_id)
        self._download(video_url, out_path)
        return ClipResult(output_path=out_path, provider=self.name, raw={"task_id": task_id})

    def _poll(self, task_id: str) -> str:
        deadline = time.monotonic() + _POLL_TIMEOUT_S
        url = f"{_BASE}{_SUBMIT}/{task_id}"
        while time.monotonic() < deadline:
            resp = requests.get(url, headers=self._headers(), timeout=30)
            resp.raise_for_status()
            data = resp.json()["data"]
            status = data.get("task_status")
            if status == "succeed":
                return data["task_result"]["videos"][0]["url"]
            if status == "failed":
                raise RuntimeError(f"Kling job {task_id} failed: {data.get('task_status_msg')}")
            time.sleep(_POLL_INTERVAL_S)
        raise TimeoutError(f"Kling job {task_id} did not finish in {_POLL_TIMEOUT_S}s.")

    @staticmethod
    def _download(url: str, out_path: str) -> None:
        with requests.get(url, stream=True, timeout=120) as r:
            r.raise_for_status()
            with open(out_path, "wb") as fh:
                for chunk in r.iter_content(chunk_size=1 << 16):
                    fh.write(chunk)
