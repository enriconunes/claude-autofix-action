"""Extract code and diffs from Claude responses."""

from __future__ import annotations

import re
from typing import Optional


def extract_code_from_response(response_text: str) -> Optional[str]:
    """Extract Python code from Claude's response."""
    # First, try to extract from markdown code fence
    code_pattern = r'```(?:python)?\s*\n(.*?)\n```'
    matches = re.findall(code_pattern, response_text, re.DOTALL | re.IGNORECASE)

    if matches:
        return matches[0].strip()

    # If no code fence, check if the response looks like Python code
    lines = response_text.strip().split('\n')
    if lines:
        first_line = lines[0].strip()
        # Check if it starts with Python-like content
        if (first_line.startswith('def ') or
            first_line.startswith('class ') or
            first_line.startswith('import ') or
            first_line.startswith('from ') or
            first_line.startswith('#') or
            first_line == '' and len(lines) > 1):
            # Looks like Python code, return the whole response
            return response_text.strip()

    return None


def extract_diff_from_response(response_text: str) -> Optional[str]:
    """Extract unified diff from Claude's response."""
    # First, try to extract from markdown code fence
    diff_pattern = r'```(?:diff)?\s*\n(--- .*?)\n```'
    matches = re.findall(diff_pattern, response_text, re.DOTALL | re.IGNORECASE)

    if matches:
        return matches[0].strip()

    # Second attempt: look for diff starting with "--- a/" or "--- "
    lines = response_text.split('\n')
    diff_lines = []
    in_diff = False

    for i, line in enumerate(lines):
        # Start capturing when we see "---" at the beginning
        if line.startswith('---') and ('a/' in line or i + 1 < len(lines) and lines[i + 1].startswith('+++')):
            in_diff = True
            diff_lines = [line]
            continue

        if in_diff:
            # Continue if line looks like part of a diff
            if (line.startswith('+++') or
                line.startswith('@@') or
                line.startswith('-') or
                line.startswith('+') or
                line.startswith(' ') or
                line.startswith('\\') or
                not line.strip()):  # Empty lines are OK in diffs
                diff_lines.append(line)
            else:
                # Stop when we hit a line that doesn't look like diff
                if len(diff_lines) > 3:  # Need at least ---, +++, @@, and one change
                    break
                else:
                    # False start, reset
                    in_diff = False
                    diff_lines = []

    if diff_lines and len(diff_lines) > 3:
        # Clean up: remove trailing empty lines
        while diff_lines and not diff_lines[-1].strip():
            diff_lines.pop()
        return '\n'.join(diff_lines)

    return None


def extract_file_path_from_diff(diff_content: str) -> Optional[str]:
    """Extract the target file path from a unified diff."""
    lines = diff_content.split('\n')
    for line in lines:
        if line.startswith('+++'):
            # Format: "+++ b/path/to/file.py"
            path = line[4:].strip()
            if path.startswith('b/'):
                path = path[2:]
            return path

    return None
