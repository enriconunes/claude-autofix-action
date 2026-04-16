#!/usr/bin/env python3
"""Generate test files for source files using Claude AI."""

from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add ci directory to path to enable imports
sys.path.insert(0, str(Path(__file__).parent))

from api import send_to_claude, resolve_generate_tests_model
from config import get_generate_tests_prompt
from file_utils import read_source
from fix.extractor import extract_code_from_response

# Source extensions that are candidates for test generation
_PY_EXTS  = {".py"}
_JS_EXTS  = {".ts", ".tsx", ".js", ".jsx"}
_ALL_EXTS = _PY_EXTS | _JS_EXTS

# Substrings that identify a file as already being a test file
_TEST_INDICATORS = ["test_", ".test.", ".spec.", "__tests__"]


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--files", nargs="+", required=True,
        help="Source file(s) to generate tests for",
    )
    parser.add_argument(
        "--framework", default="pytest", choices=["pytest", "vitest", "jest"],
        help="Test framework to use (default: pytest)",
    )
    parser.add_argument(
        "--language", default="python",
        choices=["python", "typescript", "javascript"],
        help="Source language (default: python)",
    )
    parser.add_argument(
        "--output-dir", default=None,
        help="Override output directory for all generated test files",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_test_file(path: Path) -> bool:
    """Return True if the file is itself a test/spec file."""
    name = path.name.lower()
    parts = [p.lower() for p in path.parts]
    return any(ind in name for ind in _TEST_INDICATORS) or "__tests__" in parts


def has_testable_content(source_code: str, language: str) -> bool:
    """Return True if the source file exposes public functions or classes worth testing."""
    if language == "python":
        for line in source_code.splitlines():
            stripped = line.strip()
            # Public function or class (not private _name)
            if stripped.startswith("def ") and not stripped.startswith("def _"):
                return True
            if stripped.startswith("class ") and not stripped.startswith("class _"):
                return True
        return False
    else:
        # JS / TS: look for exported symbols
        return any(kw in source_code for kw in [
            "export function",
            "export class",
            "export const",
            "export let",
            "export default",
            "module.exports",
        ])


def infer_test_path(source_path: Path, language: str, output_dir: Optional[str]) -> Path:
    """Infer where the generated test file should be saved.

    Python:  src/math.py            → tests/test_math.py
    JS/TS:   src/utils/format.ts    → src/utils/__tests__/format.test.ts
    """
    if output_dir:
        base = Path(output_dir)
        if language == "python":
            return base / f"test_{source_path.name}"
        else:
            return base / f"{source_path.stem}.test{source_path.suffix}"

    if language == "python":
        tests_dir = Path.cwd() / "tests"
        return tests_dir / f"test_{source_path.name}"
    else:
        tests_dir = source_path.parent / "__tests__"
        return tests_dir / f"{source_path.stem}.test{source_path.suffix}"


def build_payload(
    source_code: str,
    source_path: str,
    language: str,
    framework: str,
    test_path: str,
) -> Dict[str, Any]:
    """Build the Claude API payload for test generation."""
    lang_label = language.capitalize()
    prompt = get_generate_tests_prompt(language=lang_label, framework=framework)

    body = textwrap.dedent(
        f"""
        {prompt}

        ### Source file: `{source_path}`

        ```
        {source_code}
        ```

        ### Output file path
        Save the test file at: `{test_path}`
        Adjust imports to reflect the relative path between source and test files.
        """
    ).strip()

    return {
        "model": resolve_generate_tests_model(),
        "max_tokens": 8192,
        "messages": [{"role": "user", "content": body}],
    }


# ---------------------------------------------------------------------------
# Per-file processing
# ---------------------------------------------------------------------------

def process_file(
    source_file: Path,
    language: str,
    framework: str,
    api_key: str,
    output_dir: Optional[str],
) -> Dict[str, Any]:
    """Generate tests for a single source file. Returns a result dict."""
    print(f"\n{'='*60}")
    print(f"Processing: {source_file}")
    print("=" * 60)

    # Guard: skip test files
    if is_test_file(source_file):
        print("  Skipping — this is already a test file.")
        return {"file": str(source_file), "skipped": True, "reason": "already a test file"}

    # Guard: unsupported extension
    if source_file.suffix not in _ALL_EXTS:
        print(f"  Skipping — unsupported extension '{source_file.suffix}'.")
        return {"file": str(source_file), "skipped": True, "reason": "unsupported extension"}

    # Read source
    source_code = read_source(str(source_file))
    if source_code.startswith("<"):
        print(f"  Skipping — could not read file: {source_code}")
        return {"file": str(source_file), "skipped": True, "reason": "unreadable file"}

    # Guard: nothing worth testing
    if not has_testable_content(source_code, language):
        print("  Skipping — no public functions or classes found.")
        return {"file": str(source_file), "skipped": True, "reason": "no testable content"}

    # Infer test path
    test_path = infer_test_path(source_file, language, output_dir)

    # Guard: test already exists
    if test_path.exists():
        print(f"  Skipping — test already exists at: {test_path}")
        return {
            "file": str(source_file),
            "skipped": True,
            "reason": f"test already exists at {test_path}",
        }

    print(f"  Test will be saved to: {test_path}")

    # Call Claude
    payload = build_payload(
        source_code=source_code,
        source_path=str(source_file),
        language=language,
        framework=framework,
        test_path=str(test_path),
    )
    print("  Requesting tests from Claude...")

    try:
        response = send_to_claude(api_key, payload)
    except SystemExit:
        return {"file": str(source_file), "success": False, "reason": "Claude API error"}

    response_text = "".join(
        block.get("text", "")
        for block in response.get("content", [])
        if block.get("type") == "text"
    )

    # Extract code
    test_code = extract_code_from_response(response_text, language=language)
    if not test_code:
        print("  ⚠️  No valid test code found in Claude response.")
        return {"file": str(source_file), "success": False, "reason": "no test code in response"}

    # Save
    test_path.parent.mkdir(parents=True, exist_ok=True)
    test_path.write_text(test_code, encoding="utf-8")
    print(f"  ✓ Tests saved to: {test_path}")

    return {
        "file": str(source_file),
        "success": True,
        "test_file": str(test_path),
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    print(f"Using Claude model (generate tests): {resolve_generate_tests_model()}")
    print(f"Framework: {args.framework} | Language: {args.language}")

    results: List[Dict[str, Any]] = []

    for file_str in args.files:
        source_file = Path(file_str)
        if not source_file.is_absolute():
            source_file = (Path.cwd() / source_file).resolve()

        if not source_file.exists():
            print(f"\n⚠️  File not found: {source_file}")
            results.append({"file": file_str, "skipped": True, "reason": "file not found"})
            continue

        result = process_file(
            source_file=source_file,
            language=args.language,
            framework=args.framework,
            api_key=api_key,
            output_dir=args.output_dir,
        )
        results.append(result)

    # ── Summary ──────────────────────────────────────────────────────────────
    generated = [r for r in results if r.get("success")]
    skipped   = [r for r in results if r.get("skipped")]
    failed    = [r for r in results if not r.get("success") and not r.get("skipped")]

    print(f"\n{'='*60}")
    print("SUMMARY")
    print("=" * 60)
    print(f"Generated: {len(generated)} | Skipped: {len(skipped)} | Failed: {len(failed)}")

    for r in generated:
        print(f"  ✓ {r['file']} → {r['test_file']}")
    for r in skipped:
        print(f"  ⊘ {r['file']} ({r['reason']})")
    for r in failed:
        print(f"  ✗ {r['file']} ({r.get('reason', 'unknown')})")

    # Save summary JSON for the workflow to consume
    summary_dir = Path("claude-generated-tests")
    summary_dir.mkdir(exist_ok=True)
    summary_path = summary_dir / "summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "total": len(results),
                "generated": len(generated),
                "skipped": len(skipped),
                "failed": len(failed),
                "results": results,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nSummary saved to: {summary_path}")


if __name__ == "__main__":
    main()
