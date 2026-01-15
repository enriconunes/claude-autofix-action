#!/usr/bin/env python3
"""Apply automated fixes suggested by Claude for failing tests."""

from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap
from pathlib import Path
from typing import Any, Dict, List

from api import send_to_claude, resolve_model_name
from config import FIX_PROMPT
from file_utils import read_source
from fix import infer_source_file, extract_code_from_response
from pytest import load_report, extract_failures, format_longrepr


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report",
        default=".report.json",
        help="Path to the pytest JSON report",
    )
    parser.add_argument(
        "--output-dir",
        default="claude-patches",
        help="Directory to save generated patches",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Automatically apply patches after generating them",
    )
    parser.add_argument(
        "--max-fixes",
        type=int,
        default=5,
        help="Maximum number of fixes to attempt (default: 5)",
    )
    return parser.parse_args()


def build_fix_payload(
    failure: Dict[str, Any],
    report: Dict[str, Any],
    index: int,
    source_file_path: str
) -> Dict[str, Any]:
    """Build API payload for Claude to generate fix."""
    source_code = read_source(source_file_path)
    longrepr = failure.get("longrepr")
    traceback_text = format_longrepr(longrepr)
    failure_json = json.dumps(failure, indent=2, ensure_ascii=False)

    body = textwrap.dedent(
        f"""
        {FIX_PROMPT}

        ### Failing Test #{index}
        - **Node ID:** {failure.get('nodeid', 'unknown')}
        - **Test Outcome:** {failure.get('outcome')}
        - **Source File to Fix:** {source_file_path}

        ### Python Source Code (ORIGINAL FILE - PRESERVE ALL CODE)
        ```python
        {source_code}
        ```

        ### Test Failure Information
        ```json
        {failure_json}
        ```

        ### Traceback and Error Messages
        ```
        {traceback_text}
        ```

        Remember: Return the COMPLETE file with ALL original code preserved, only fixing the bug.
        """
    ).strip()

    return {
        "model": resolve_model_name(),
        "max_tokens": 4096,
        "messages": [
            {
                "role": "user",
                "content": body
            }
        ]
    }


def process_failure(
    failure: Dict[str, Any],
    report: Dict[str, Any],
    index: int,
    api_key: str,
    output_dir: Path,
    apply_fixes: bool
) -> Dict[str, Any]:
    """Process a single test failure and generate/apply fix."""
    nodeid = failure.get('nodeid', 'unknown')
    print(f"\n{'='*60}")
    print(f"Processing failure {index}: {nodeid}")
    print('='*60)

    # Infer source file from test name
    source_path = infer_source_file(failure)

    if not source_path:
        print(f"⚠️  Could not determine source file path for {nodeid}")
        print(f"  Debug - nodeid: {nodeid}")
        print(f"  Debug - working directory: {Path.cwd()}")
        return {
            'nodeid': nodeid,
            'success': False,
            'reason': 'Could not determine source file path',
        }

    # Convert to absolute path
    source_file = Path(source_path)
    if not source_file.is_absolute():
        source_file = (Path.cwd() / source_file).resolve()

    print(f"  Target file: {source_file}")

    # Get fix from Claude
    payload = build_fix_payload(failure, report, index, str(source_file))
    print(f"Requesting fix from Claude...")

    try:
        response = send_to_claude(api_key, payload)
    except SystemExit:
        print(f"Failed to get response from Claude for {nodeid}")
        return {
            'nodeid': nodeid,
            'success': False,
            'reason': 'Claude API error',
        }

    # Extract response text
    response_text = ""
    content = response.get("content", [])
    for block in content:
        if block.get("type") == "text":
            text = block.get("text", "")
            if text:
                response_text += text + "\n"

    # Save full response for debugging
    debug_file = output_dir / f"{index:02d}_response.txt"
    debug_file.write_text(response_text, encoding='utf-8')
    print(f"  Debug: Full response saved to {debug_file}")

    # Extract Python code from response
    fixed_code = extract_code_from_response(response_text)

    if not fixed_code:
        print(f"⚠️  No valid Python code found in Claude response for {nodeid}")
        print(f"  Check {debug_file} for the full response")
        return {
            'nodeid': nodeid,
            'success': False,
            'reason': 'No Python code in response',
            'debug_file': str(debug_file),
        }

    print(f"  Code preview:")
    print("  " + "\n  ".join(fixed_code.split('\n')[:5]))

    # Save the fixed code
    fixed_filename = f"{index:02d}_{source_file.name}"
    fixed_path = output_dir / fixed_filename
    fixed_path.write_text(fixed_code, encoding='utf-8')
    print(f"✓ Saved fixed code to: {fixed_path}")

    # Apply fix if requested
    if apply_fixes:
        print(f"Applying fix to {source_file}...")
        try:
            # Write the fixed code directly (git handles versioning)
            source_file.write_text(fixed_code, encoding='utf-8')
            print(f"✓ Successfully applied fix to {source_file}")
        except Exception as e:
            print(f"✗ Failed to apply fix: {e}")
            return {
                'nodeid': nodeid,
                'success': False,
                'fixed_file': str(fixed_path),
                'reason': f'Failed to write file: {e}',
            }

    return {
        'nodeid': nodeid,
        'success': True,
        'fixed_file': str(fixed_path),
        'target_file': str(source_file),
    }


def main() -> None:
    """Main entry point for claude_fix."""
    args = parse_args()

    report = load_report(args.report)
    failures = extract_failures(report)

    if not failures:
        print("No failing tests found in report. Nothing to fix.")
        return

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    model_name = resolve_model_name()
    print(f"Using Claude model: {model_name}")

    # Limit number of fixes to prevent overwhelming changes
    failures_to_fix = failures[:args.max_fixes]

    if len(failures) > args.max_fixes:
        print(f"Limiting fixes to first {args.max_fixes} failures (out of {len(failures)} total)")

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)
    print(f"Saving patches to: {output_dir}")

    successful_patches: List[Dict[str, Any]] = []
    failed_patches: List[Dict[str, Any]] = []

    # Process each failure
    for index, failure in enumerate(failures_to_fix, start=1):
        result = process_failure(failure, report, index, api_key, output_dir, args.apply)

        if result['success']:
            successful_patches.append(result)
        else:
            failed_patches.append(result)

    # Print summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print('='*60)
    print(f"Total failures processed: {len(failures_to_fix)}")
    print(f"Patches generated: {len(successful_patches)}")
    print(f"Failed to generate/apply: {len(failed_patches)}")

    if successful_patches:
        print("\n✓ Successful patches:")
        for patch in successful_patches:
            print(f"  - {patch['nodeid']}")
            print(f"    File: {patch.get('target_file', 'unknown')}")
            print(f"    Patch: {patch['fixed_file']}")

    if failed_patches:
        print("\n✗ Failed patches:")
        for patch in failed_patches:
            print(f"  - {patch['nodeid']}")
            print(f"    Reason: {patch['reason']}")

    # Save summary as JSON for workflow
    summary_path = output_dir / "summary.json"
    summary_data = {
        'total_failures': len(failures),
        'processed': len(failures_to_fix),
        'successful': len(successful_patches),
        'failed': len(failed_patches),
        'patches': successful_patches,
        'errors': failed_patches,
    }
    summary_path.write_text(json.dumps(summary_data, indent=2), encoding='utf-8')
    print(f"\nSummary saved to: {summary_path}")

    # Don't exit with error - let the workflow decide what to do
    if not successful_patches:
        print("\n⚠️  No patches were successfully generated/applied.")
        print("This may be because:")
        print("  - The Claude API couldn't generate valid patches")
        print("  - The patches couldn't be applied cleanly")
        print("  - There were API errors")
        sys.exit(0)


if __name__ == "__main__":
    main()
