"""Runway Gen-3 adapter -- first + last frame conditioning.

Runway's image-to-video takes a set of `promptImage` entries tagged by
position; we send one at position "first" (start frame) and one at "last"
(end frame). Same truthful-endpoints contract as every other provider.

Uses the async task pattern (create -> poll -> download). Set RUNWAY_API_KEY.
Adjust the model id / API version constants if Runway bumps them; nothing else
in the pipeline needs to change.
"""

from __future__ import annotations

import base64
import mimetypes
import os
import time

import requests

from .base import ClipRequest, ClipResult, VideoProvider

_BASE = os.environ.get("RUNWAY_BASE_URL", "https://api.dev.runwayml.com")
_VERSION = "2024-11-06"
_POLL_TIMEOUT_S = 600
_POLL_INTERVAL_S = 6


def _data_uri(path: str) -> str:
    mime = mimetypes.guess_type(path)[0] or "image/jpeg"
    with open(path, "rb") as fh:
        b64 = base64.b64encode(fh.read()).decode("ascii")
    return f"data:{mime};base64,{b64}"


class RunwayProvider(VideoProvider):
    name = "runway"

    def __init__(self, api_key: str | None = None, model: str = "gen3a_turbo") -> None:
        self.api_key = api_key or os.environ.get("RUNWAY_API_KEY")
        if not self.api_key:
            raise RuntimeError("Set RUNWAY_API_KEY or pass api_key=.")
        self.model = model

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "X-Runway-Version": _VERSION,
            "Content-Type": "application/json",
        }

    def generate_clip(self, request: ClipRequest, out_path: str) -> ClipResult:
        payload = {
            "model": self.model,
            "promptImage": [
                {"uri": _data_uri(request.start_image), "position": "first"},
                {"uri": _data_uri(request.end_image), "position": "last"},
            ],
            "promptText": request.prompt,
            "duration": int(round(request.duration_s)),
            "ratio": "1280:768",
        }
        submit = requests.post(
            f"{_BASE}/v1/image_to_video", json=payload, headers=self._headers(), timeout=60
        )
        submit.raise_for_status()
        task_id = submit.json()["id"]

        video_url = self._poll(task_id)
        self._download(video_url, out_path)
        return ClipResult(output_path=out_path, provider=self.name, raw={"id": task_id})

    def _poll(self, task_id: str) -> str:
        deadline = time.monotonic() + _POLL_TIMEOUT_S
        url = f"{_BASE}/v1/tasks/{task_id}"
        while time.monotonic() < deadline:
            resp = requests.get(url, headers=self._headers(), timeout=30)
            resp.raise_for_status()
            data = resp.json()
            status = data.get("status")
            if status == "SUCCEEDED":
                return data["output"][0]
            if status in {"FAILED", "CANCELLED"}:
                raise RuntimeError(f"Runway task {task_id} {status}: {data.get('failure')}")
            time.sleep(_POLL_INTERVAL_S)
        raise TimeoutError(f"Runway task {task_id} did not finish in {_POLL_TIMEOUT_S}s.")

    @staticmethod
    def _download(url: str, out_path: str) -> None:
        with requests.get(url, stream=True, timeout=120) as r:
            r.raise_for_status()
            with open(out_path, "wb") as fh:
                for chunk in r.iter_content(chunk_size=1 << 16):
                    fh.write(chunk)
