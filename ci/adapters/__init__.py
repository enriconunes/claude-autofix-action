"""Test framework adapters for claude-autofix."""

from __future__ import annotations

from adapters.base import TestAdapter


def get_adapter(framework: str, language: str = "python") -> TestAdapter:
    """Return the correct adapter for the given framework and language.

    Args:
        framework: "pytest", "vitest", or "jest"
        language:  "python", "typescript", or "javascript"

    Returns:
        A TestAdapter instance ready to use.
    """
    framework = framework.lower().strip()
    language = language.lower().strip()

    if framework == "pytest":
        from adapters.pytest_adapter import PytestAdapter
        return PytestAdapter()

    if framework in ("vitest", "jest"):
        from adapters.vitest_adapter import VitestAdapter
        return VitestAdapter(language=language)

    raise ValueError(
        f"Unknown test framework '{framework}'. "
        "Supported values: pytest, vitest, jest"
    )


__all__ = ["TestAdapter", "get_adapter"]
