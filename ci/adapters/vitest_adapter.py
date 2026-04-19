"""Vitest / Jest adapter for JavaScript and TypeScript projects."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure the ci/ directory is on the path when this module is imported standalone
sys.path.insert(0, str(Path(__file__).parent.parent))

from adapters.base import TestAdapter


# JS/TS test file suffixes and their corresponding source extensions
_TEST_SUFFIXES = [
    ".test.ts",
    ".test.tsx",
    ".test.js",
    ".test.jsx",
    ".spec.ts",
    ".spec.tsx",
    ".spec.js",
    ".spec.jsx",
]


def _infer_js_source_file(test_file_path: str) -> Optional[str]:
    """Infer the JS/TS source file path from a test file path.

    Search order for a test at ``dir/foo.test.ts``:
    1. Same directory         → dir/foo.ts
    2. Parent directory       → dir/../foo.ts   (covers __tests__/ conventions)
    3. src/ at project root   → <cwd>/src/foo.ts
    4. app/ at project root   → <cwd>/app/foo.ts  (Next.js app router)
    5. lib/ at project root   → <cwd>/lib/foo.ts
    6. Project root           → <cwd>/foo.ts
    """
    test_path = Path(test_file_path)
    name = test_path.name

    for suffix in _TEST_SUFFIXES:
        if name.endswith(suffix):
            # Derive the source file extension from the test suffix
            # e.g. ".test.ts" → ".ts", ".spec.tsx" → ".tsx"
            source_ext = "." + suffix.lstrip(".").split(".")[-1]
            base_name = name[: -len(suffix)]
            source_name = base_name + source_ext

            search_paths = [
                test_path.parent / source_name,
                test_path.parent.parent / source_name,
                Path.cwd() / "src" / source_name,
                Path.cwd() / "app" / source_name,
                Path.cwd() / "lib" / source_name,
                Path.cwd() / source_name,
            ]

            for candidate in search_paths:
                if candidate.exists() and candidate.is_file():
                    print(f"  Inferred JS/TS source file: {candidate}")
                    return str(candidate)

            # Not found on disk — return the most likely path (same dir) as a hint
            hint = test_path.parent / source_name
            print(f"  ⚠️  Source file not found on disk; guessing: {hint}")
            return str(hint)

    return None


class VitestAdapter(TestAdapter):
    """Adapter for Vitest and Jest (JavaScript / TypeScript projects).

    Supports the JSON reporter output produced by:
      vitest run --reporter=json --outputFile=.report.json
      jest     --json           --outputFile=.report.json
    """

    def __init__(self, language: str = "typescript") -> None:
        """
        Args:
            language: "typescript" or "javascript" — affects prompts and
                      the preferred source file extension.
        """
        self._language = language.lower()

    # ------------------------------------------------------------------
    # TestAdapter interface
    # ------------------------------------------------------------------

    def parse_report(self, path: str) -> Dict[str, Any]:
        """Load the Vitest/Jest JSON report."""
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except FileNotFoundError:
            print(f"Report not found at {path}", file=sys.stderr)
            raise SystemExit(1)

    def extract_failures(self, report: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract normalised failure dicts from a Vitest/Jest report.

        Normalised dict keys (mirrors pytest adapter output where possible):
            nodeid          – unique test identifier
            outcome         – always "failed"
            test_file       – absolute path to the test file
            title           – test title
            ancestor_titles – list of describe block names
            failure_message – concatenated failure messages
            location        – {"line": int, "column": int} or None
        """
        failures: List[Dict[str, Any]] = []

        for suite in report.get("testResults", []):
            test_file = suite.get("testFilePath", "")
            for assertion in suite.get("assertionResults", []):
                if assertion.get("status") != "failed":
                    continue

                ancestor_titles: List[str] = assertion.get("ancestorTitles", [])
                title: str = assertion.get("title", "unknown")

                # Build a pytest-style nodeid for compatibility with the rest of the pipeline
                parts = [test_file] + ancestor_titles + [title]
                nodeid = "::".join(p for p in parts if p)

                failures.append(
                    {
                        "nodeid": nodeid,
                        "outcome": "failed",
                        "test_file": test_file,
                        "title": title,
                        "ancestor_titles": ancestor_titles,
                        "failure_message": "\n".join(
                            assertion.get("failureMessages", [])
                        ),
                        "location": assertion.get("location"),
                    }
                )

        return failures

    def format_failure(self, failure: Dict[str, Any]) -> str:
        """Format a Vitest/Jest failure for display and prompt building."""
        lines: List[str] = []

        if failure.get("ancestor_titles"):
            lines.append("Describe: " + " > ".join(failure["ancestor_titles"]))

        lines.append(f"Test:      {failure.get('title', 'unknown')}")

        location = failure.get("location")
        if location:
            lines.append(
                f"Location:  {failure.get('test_file', '')}:"
                f"{location.get('line', '?')}:{location.get('column', '?')}"
            )

        msg = failure.get("failure_message", "")
        if msg:
            lines.append("")
            lines.append("Failure message:")
            lines.append(msg)

        return "\n".join(lines)

    def infer_source_file(self, failure: Dict[str, Any]) -> Optional[str]:
        test_file = failure.get("test_file", "")
        return _infer_js_source_file(test_file) if test_file else None

    def get_language(self) -> str:
        return "TypeScript" if self._language == "typescript" else "JavaScript"

    def get_extension(self) -> str:
        return ".ts" if self._language == "typescript" else ".js"
