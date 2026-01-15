"""Format pytest report data for display and analysis."""

from __future__ import annotations

import json
from typing import Any, Dict, List


def format_longrepr(longrepr: Any) -> str:
    """Format pytest longrepr (traceback) into readable text."""
    if isinstance(longrepr, str):
        return longrepr
    if not isinstance(longrepr, dict):
        return json.dumps(longrepr, indent=2, ensure_ascii=False)

    lines: List[str] = []

    # Extract traceback entries
    reprtraceback = longrepr.get("reprtraceback")
    if isinstance(reprtraceback, dict):
        for entry in reprtraceback.get("reprentries", []):
            data = entry.get("data")
            if data:
                lines.append(data)
            file_loc = entry.get("reprfileloc")
            if isinstance(file_loc, dict):
                path = file_loc.get("path")
                lineno = file_loc.get("lineno")
                message = file_loc.get("message")
                location = ":".join(
                    str(part)
                    for part in (path, lineno, message)
                    if part not in (None, "")
                )
                if location:
                    lines.append(location)

    # Extract crash information
    reprcrash = longrepr.get("reprcrash")
    if isinstance(reprcrash, dict):
        crash_path = reprcrash.get("path")
        crash_lineno = reprcrash.get("lineno")
        crash_message = reprcrash.get("message")
        crash_line = ":".join(
            str(part)
            for part in (crash_path, crash_lineno, crash_message)
            if part not in (None, "")
        )
        if crash_line:
            lines.append(crash_line)

    # Extract additional sections
    sections = longrepr.get("sections")
    if isinstance(sections, list):
        for section in sections:
            if isinstance(section, list) and len(section) == 2:
                title, content = section
                lines.append(f"{title}\n{content}")

    return "\n".join(lines)


def extract_response_text(response: Dict[str, Any]) -> str:
    """Extract concatenated text from Claude API response."""
    texts: List[str] = []
    content = response.get("content", [])

    for block in content:
        if block.get("type") == "text":
            text = block.get("text", "")
            if text.strip():
                texts.append(text.strip())

    combined = "\n\n".join(texts).strip()
    return combined


def build_comment_section(failure: Dict[str, Any], body: str) -> str:
    """Generate a Markdown section for a specific failing test."""
    nodeid = failure.get("nodeid") or failure.get("name") or "failing test"
    header = f"### Claude analysis for `{nodeid}`"
    return f"{header}\n\n{body.strip()}"
