"""Claude model resolution and configuration."""

from __future__ import annotations

import os
from typing import Iterator

# Handle both relative and absolute imports
try:
    from ..config import DEFAULT_CLAUDE_MODEL, FALLBACK_MODELS
except ImportError:
    from config import DEFAULT_CLAUDE_MODEL, FALLBACK_MODELS


def normalize_model_name(model_name: str) -> str:
    """Ensure the Claude model name is valid."""
    return model_name.strip()


def resolve_model_name() -> str:
    """Return the Claude model name, allowing override via CLAUDE_MODEL env var."""
    configured_name = os.environ.get("CLAUDE_MODEL", DEFAULT_CLAUDE_MODEL)
    if not configured_name or not configured_name.strip():
        configured_name = DEFAULT_CLAUDE_MODEL
    return normalize_model_name(configured_name)


def iter_candidate_models(model_name: str) -> Iterator[str]:
    """Yield model name variants to improve compatibility."""
    yielded = set()

    # Try original model first
    if model_name and model_name not in yielded:
        yielded.add(model_name)
        yield model_name

    # Then try fallback models
    for fallback in FALLBACK_MODELS:
        if fallback not in yielded:
            yielded.add(fallback)
            yield fallback
