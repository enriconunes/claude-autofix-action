"""File utilities for reading source code."""

from __future__ import annotations

from pathlib import Path
from typing import Optional


def read_source(path: Optional[str]) -> str:
    """Read source code from file with fallback encoding."""
    if not path:
        return "<Source path not provided by pytest>"

    repo_root = Path.cwd()
    resolved_path = Path(path)
    if not resolved_path.is_absolute():
        resolved_path = (repo_root / resolved_path).resolve()

    if not resolved_path.exists():
        return f"<Unable to locate source file at {resolved_path}>"

    try:
        return resolved_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return resolved_path.read_text(encoding="latin-1")
