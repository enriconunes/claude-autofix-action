#!/usr/bin/env python3
"""Send failing test results to Claude for automated analysis."""

from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap
from pathlib import Path
from typing import Any, Dict, List

# Add ci directory to path to enable imports
sys.path.insert(0, str(Path(__file__).parent))

from api import send_to_claude, send_health_check, resolve_comment_model
from config import BASE_ANALYSIS_PROMPT
from file_utils import read_source
from pytest import extract_response_text, build_comment_section
from adapters import get_adapter


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report",
        default=".report.json",
        help="Path to the test JSON report.",
    )
    parser.add_argument(
        "--comment-file",
        default=None,
        help="If provided, write a Markdown summary suitable for a PR comment to this path.",
    )
    parser.add_argument(
        "--framework",
        default="pytest",
        choices=["pytest", "vitest", "jest"],
        help="Test framework used to generate the report (default: pytest)",
    )
    parser.add_argument(
        "--language",
        default="python",
        choices=["python", "typescript", "javascript"],
        help="Source language of the project (default: python)",
    )
    return parser.parse_args()


def build_payload(
    failure: Dict[str, Any],
    report: Dict[str, Any],
    index: int,
    adapter: Any,
) -> Dict[str, Any]:
    """Build API payload for Claude from a test failure."""
    # Get source file path via the adapter
    source_path = adapter.infer_source_file(failure)
    source_code = read_source(source_path)
    traceback_text = adapter.format_failure(failure)
    language = adapter.get_language()

    failure_json = json.dumps(failure, indent=2, ensure_ascii=False)

    rel_path = source_path
    if source_path:
        try:
            rel_path = os.path.relpath(Path(source_path).resolve(), Path.cwd())
        except OSError:
            rel_path = source_path

    body = textwrap.dedent(
        f"""
        {BASE_ANALYSIS_PROMPT}

        ### Failing Test #{index}
        - **Node ID:** {failure.get('nodeid', 'unknown')}
        - **Test Outcome:** {failure.get('outcome')}
        - **Source File:** {rel_path or 'unknown'}

        ### {language} Source Code
        ```
        {source_code}
        ```

        ### Test Failure (JSON excerpt)
        ```json
        {failure_json}
        ```

        ### Traceback and Error Messages
        ```
        {traceback_text}
        ```
        """
    ).strip()

    return {
        "model": resolve_comment_model(),
        "max_tokens": 4096,
        "messages": [
            {
                "role": "user",
                "content": body,
            }
        ]
    }


def main() -> None:
    """Main entry point for claude_report."""
    args = parse_args()

    # Select the right adapter for the chosen framework / language
    adapter = get_adapter(args.framework, args.language)
    print(f"Framework: {args.framework} | Language: {adapter.get_language()}")

    report = adapter.parse_report(args.report)
    failures = adapter.extract_failures(report)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    model_name = resolve_comment_model()
    print(f"Using Claude model (comment): {model_name}")

    # Handle case with no failures
    if not failures:
        print("All tests passed. No failing tests were recorded.")

        if not api_key:
            print("ANTHROPIC_API_KEY environment variable is not set; skipping Claude health check.")
            return

        send_health_check(api_key, model_name)
        return

    # Ensure API key is available
    if not api_key:
        print("ANTHROPIC_API_KEY environment variable is not set.", file=sys.stderr)
        raise SystemExit(1)

    # Process all failures
    comment_sections: List[str] = []

    for index, failure in enumerate(failures, start=1):
        payload = build_payload(failure, report, index, adapter)
        print(f"Sending failure #{index} to Claude...")
        response = send_to_claude(api_key, payload)
        print(json.dumps(response, indent=2, ensure_ascii=False))

        comment_body = extract_response_text(response)
        if comment_body:
            comment_sections.append(build_comment_section(failure, comment_body))

    # Write comment file if requested
    if args.comment_file and comment_sections:
        comment_text = "\n\n---\n\n".join(comment_sections).strip()
        comment_path = Path(args.comment_file)
        comment_path.write_text(f"{comment_text}\n", encoding="utf-8")
        print(f"Claude analysis written to {comment_path}")
    elif args.comment_file:
        comment_path = Path(args.comment_file)
        if comment_path.exists():
            comment_path.unlink()
        print("No Claude analysis generated; comment file removed if it existed.")


if __name__ == "__main__":
    main()
