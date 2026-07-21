"""Cardinal Lust multi-angle reel pipeline.

Turn a photographer's multi-angle room shots into truthful walkthrough reels by
using real photos as the start and end frames of keyframe interpolation, so the
model only fills short, plausible in-betweens instead of hallucinating whole
rooms.
"""

from .pipeline import PipelineResult, RoomResult, run

__all__ = ["run", "PipelineResult", "RoomResult"]
__version__ = "0.1.0"
