"""Claude model resolution and configuration."""

from __future__ import annotations

from typing import Iterator

# Handle both relative and absolute imports
try:
    from ..config import (
        COMMENT_CLAUDE_MODEL, FIX_CLAUDE_MODEL,
        GENERATE_TESTS_CLAUDE_MODEL, FALLBACK_MODELS,
    )
except ImportError:
    from config import (
        COMMENT_CLAUDE_MODEL, FIX_CLAUDE_MODEL,
        GENERATE_TESTS_CLAUDE_MODEL, FALLBACK_MODELS,
    )


def resolve_comment_model() -> str:
    """Return the model to use for PR comment analysis (claude_report.py)."""
    return COMMENT_CLAUDE_MODEL.strip()


def resolve_fix_model() -> str:
    """Return the model to use for code fix generation (claude_fix.py)."""
    return FIX_CLAUDE_MODEL.strip()


def resolve_generate_tests_model() -> str:
    """Return the model to use for test generation (claude_generate_tests.py)."""
    return GENERATE_TESTS_CLAUDE_MODEL.strip()


def iter_candidate_models(model_name: str) -> Iterator[str]:
    """Yield the given model name then fallbacks, for retry logic in the API client."""
    yielded = set()

    if model_name and model_name not in yielded:
        yielded.add(model_name)
        yield model_name

    for fallback in FALLBACK_MODELS:
        if fallback not in yielded:
            yielded.add(fallback)
            yield fallback
