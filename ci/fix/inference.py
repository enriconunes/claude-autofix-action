"""Infer source files from test names and failure information."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional


def infer_source_file(failure: Dict[str, Any]) -> Optional[str]:
    """
    Infer source file path from test failure information.

    Strategy:
    1. Try to infer from nodeid (test_module.py -> module.py)
    2. Fall back to extracting from longrepr/reprcrash
    """
    nodeid = failure.get('nodeid', '')
    source_path = None

    # First, check if we can infer from nodeid
    # nodeid format: "test_module.py::test_function"
    nodeid_parts = nodeid.split("::")
    if nodeid_parts:
        test_file = nodeid_parts[0]  # e.g. "tests/test_dividir.py" or "test_dividir.py"
        test_file_path = Path(test_file)
        test_filename = test_file_path.name  # always just "test_dividir.py"

        # If it's a test file like "test_dividir.py", try to find "dividir.py"
        if test_filename.startswith("test_") and test_filename.endswith(".py"):
            potential_source = test_filename.replace("test_", "", 1)

            # Try multiple locations for the source file
            search_paths = [
                Path(potential_source),  # Same directory
                Path.cwd() / potential_source,  # From working directory
                Path.cwd() / "functions" / potential_source,  # functions/ folder
                Path.cwd() / "src" / potential_source,  # src/ folder
                test_file_path.parent / potential_source,  # same dir as test file
                test_file_path.parent.parent / potential_source,  # parent of test dir
            ]

            for search_path in search_paths:
                if search_path.exists() and search_path.is_file():
                    source_path = str(search_path)
                    print(f"  Inferred source file from test name: {source_path}")
                    return source_path

    # Fallback: try to extract from longrepr
    longrepr = failure.get("longrepr")
    reprcrash = longrepr.get("reprcrash") if isinstance(longrepr, dict) else None
    fallback_path = reprcrash.get("path") if isinstance(reprcrash, dict) else None

    # If fallback is a test file, try to find the actual module
    if fallback_path and "test_" in fallback_path:
        fallback_file = Path(fallback_path).name
        if fallback_file.startswith("test_"):
            potential_source = fallback_file.replace("test_", "", 1)
            fallback_dir = Path(fallback_path).parent

            # Try multiple locations
            search_paths = [
                fallback_dir / potential_source,
                Path(potential_source),
                Path.cwd() / potential_source,
            ]

            for search_path in search_paths:
                if search_path.exists() and search_path.is_file():
                    source_path = str(search_path)
                    print(f"  Inferred source file from test path: {source_path}")
                    return source_path

    # Last resort: return the fallback path as-is
    return fallback_path
