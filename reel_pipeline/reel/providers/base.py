"""The one interface every video model plugs into.

The whole pipeline talks to `VideoProvider`, never to a specific vendor. To
add or switch models you implement one method. Every provider takes two REAL
photos (start + end) and returns a rendered clip -- that contract is what keeps
the reel truthful: the endpoints are always the photographer's actual frames.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass


@dataclass
class ClipRequest:
    start_image: str        # local path to the real start frame
    end_image: str          # local path to the real end frame
    duration_s: float = 3.0
    # A gentle motion hint. Keep it about camera movement, NOT scene content,
    # so the model dollies through the real geometry instead of redecorating.
    prompt: str = "slow smooth cinematic camera move through the room, no distortion"
    fps: int = 24


@dataclass
class ClipResult:
    output_path: str        # local path to the rendered clip
    provider: str
    raw: dict | None = None  # vendor response, for debugging / cost tracking


class VideoProvider(abc.ABC):
    """Implement one method to support a new video model."""

    name: str = "base"

    @abc.abstractmethod
    def generate_clip(self, request: ClipRequest, out_path: str) -> ClipResult:
        """Render start->end keyframe interpolation to `out_path`."""
        raise NotImplementedError

    def supports_keyframes(self) -> bool:
        """Whether the model accepts BOTH a start and end frame.

        If False, the pipeline degrades to single-image conditioning on the
        start frame -- more hallucination, so we warn when this happens.
        """
        return True
