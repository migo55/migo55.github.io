"""Provider registry: pick a video model by name."""

from __future__ import annotations

from .base import ClipRequest, ClipResult, VideoProvider
from .mock import MockProvider


def get_provider(name: str, **kwargs) -> VideoProvider:
    """Factory so the CLI/pipeline never imports a vendor module directly.

    Vendor adapters are imported lazily so you only need the API key (and the
    `requests` dependency path) for the provider you actually use.
    """
    name = name.lower()
    if name == "mock":
        return MockProvider()
    if name == "kling":
        from .kling import KlingProvider
        return KlingProvider(**kwargs)
    if name == "runway":
        from .runway import RunwayProvider
        return RunwayProvider(**kwargs)
    if name == "luma":
        from .luma import LumaProvider
        return LumaProvider(**kwargs)
    raise ValueError(f"Unknown provider '{name}'. Try: mock, kling, runway, luma.")


__all__ = [
    "ClipRequest",
    "ClipResult",
    "VideoProvider",
    "MockProvider",
    "get_provider",
]
