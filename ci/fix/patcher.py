"""Patch validation and application."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any, Dict, Tuple


def validate_diff(diff_content: str) -> Tuple[bool, str]:
    """Validate that the diff is in proper unified diff format."""
    if not diff_content:
        return False, "Empty diff"

    lines = diff_content.split('\n')

    # Check for required headers
    has_minus = any(line.startswith('---') for line in lines)
    has_plus = any(line.startswith('+++') for line in lines)
    has_hunk = any(line.startswith('@@') for line in lines)

    if not (has_minus and has_plus and has_hunk):
        return False, "Missing required diff headers (---, +++, or @@)"

    return True, "Valid"


def apply_patch(patch_content: str, patch_file: Path) -> Tuple[bool, str]:
    """Apply a patch using git apply."""
    try:
        # Try git apply first (more forgiving)
        result = subprocess.run(
            ['git', 'apply', '--verbose', str(patch_file)],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            return True, f"Successfully applied patch:\n{result.stdout}"

        # If git apply fails, try with --3way for better conflict resolution
        result = subprocess.run(
            ['git', 'apply', '--3way', '--verbose', str(patch_file)],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            return True, f"Successfully applied patch with 3-way merge:\n{result.stdout}"

        return False, f"Failed to apply patch:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"

    except subprocess.TimeoutExpired:
        return False, "Patch application timed out"
    except Exception as e:
        return False, f"Error applying patch: {e}"


def generate_patch_filename(failure: Dict[str, Any], index: int) -> str:
    """Generate a descriptive filename for a patch."""
    nodeid = failure.get('nodeid', 'unknown')
    # Sanitize nodeid for use in filename
    safe_name = re.sub(r'[^\w\-\.]', '_', nodeid)
    safe_name = safe_name[:50]  # Limit length

    return f"{index:02d}_{safe_name}.patch"
