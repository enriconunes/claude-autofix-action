#!/usr/bin/env python3
"""Apply automated fixes suggested by Gemini for failing tests."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Reuse utilities from gemini_report
from gemini_report import (
    build_payload,
    extract_failures,
    load_report,
    resolve_model_name,
    send_to_gemini,
)

FIX_PROMPT = textwrap.dedent(
    """
    You are an automated code-repair agent. Your ONLY task is to generate a valid unified diff patch.

    ### CRITICAL: OUTPUT ONLY THE DIFF
    - Do NOT include explanations before or after the diff
    - Do NOT include markdown code fences
    - Do NOT include any text except the diff itself
    - Start your response directly with "--- a/"

    ### REQUIRED FORMAT (example):
    --- a/path/to/file.py
    +++ b/path/to/file.py
    @@ -10,7 +10,7 @@ def function_name():
         context line
         context line
    -    return wrong_value
    +    return correct_value
         context line
         context line

    ### RULES:
    1. Use paths relative to repository root (e.g., `main.py` not `/home/user/main.py`)
    2. Include 3 lines of context before and after changes
    3. Make MINIMAL changes - only fix the failing test
    4. The patch must apply cleanly with `git apply`
    5. Do NOT add comments, explanations, or any text outside the diff format

    Now generate ONLY the unified diff to fix the failing test.
    """
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report",
        default=".report.json",
        help="Path to the pytest JSON report",
    )
    parser.add_argument(
        "--output-dir",
        default="gemini-patches",
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


def extract_diff_from_response(response_text: str) -> Optional[str]:
    """Extract the unified diff from Gemini's response."""

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
                # But only if we already have some content
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


def build_fix_payload(failure: Dict[str, Any], report: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Build a payload specifically for requesting fixes."""

    # Reuse the base payload builder
    base_payload = build_payload(failure, report, index)

    # Replace the prompt with fix-focused prompt
    base_payload['contents'][0]['parts'][0]['text'] = (
        FIX_PROMPT + "\n\n" + base_payload['contents'][0]['parts'][0]['text']
    )

    return base_payload


def generate_patch_filename(failure: Dict[str, Any], index: int) -> str:
    """Generate a descriptive filename for a patch."""

    nodeid = failure.get('nodeid', 'unknown')
    # Sanitize nodeid for use in filename
    safe_name = re.sub(r'[^\w\-\.]', '_', nodeid)
    safe_name = safe_name[:50]  # Limit length

    return f"{index:02d}_{safe_name}.patch"


def main() -> None:
    args = parse_args()

    report = load_report(args.report)
    failures = extract_failures(report)

    if not failures:
        print("No failing tests found in report. Nothing to fix.")
        return

    api_key = os.environ.get("GEMINI_KEY")
    if not api_key:
        print("ERROR: GEMINI_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    model_name = resolve_model_name()
    print(f"Using Gemini model: {model_name}")

    # Limit number of fixes to prevent overwhelming changes
    failures_to_fix = failures[:args.max_fixes]

    if len(failures) > args.max_fixes:
        print(f"Limiting fixes to first {args.max_fixes} failures (out of {len(failures)} total)")

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)
    print(f"Saving patches to: {output_dir}")

    successful_patches = []
    failed_patches = []

    for index, failure in enumerate(failures_to_fix, start=1):
        nodeid = failure.get('nodeid', 'unknown')
        print(f"\n{'='*60}")
        print(f"Processing failure {index}/{len(failures_to_fix)}: {nodeid}")
        print('='*60)

        # Get fix from Gemini
        payload = build_fix_payload(failure, report, index)
        print(f"Requesting fix from Gemini...")

        try:
            response = send_to_gemini(api_key, payload, model_name)
        except SystemExit:
            print(f"Failed to get response from Gemini for {nodeid}")
            failed_patches.append({
                'nodeid': nodeid,
                'reason': 'Gemini API error',
            })
            continue

        # Extract response text
        response_text = ""
        for candidate in response.get("candidates", []):
            content = candidate.get("content") or {}
            parts = content.get("parts") or []
            for part in parts:
                text = part.get("text")
                if text:
                    response_text += text + "\n"

        # Save full response for debugging
        debug_file = output_dir / f"{index:02d}_response.txt"
        debug_file.write_text(response_text, encoding='utf-8')
        print(f"  Debug: Full response saved to {debug_file}")

        # Extract diff
        diff = extract_diff_from_response(response_text)

        if not diff:
            print(f"⚠️  No valid diff found in Gemini response for {nodeid}")
            print(f"  Check {debug_file} for the full response")
            failed_patches.append({
                'nodeid': nodeid,
                'reason': 'No diff in response',
                'debug_file': str(debug_file),
            })
            continue

        # Validate diff
        is_valid, validation_msg = validate_diff(diff)
        if not is_valid:
            print(f"⚠️  Invalid diff format: {validation_msg}")
            print(f"  Extracted diff preview:")
            print("  " + "\n  ".join(diff.split('\n')[:10]))
            failed_patches.append({
                'nodeid': nodeid,
                'reason': f'Invalid diff: {validation_msg}',
            })
            continue

        # Save patch to file
        patch_filename = generate_patch_filename(failure, index)
        patch_path = output_dir / patch_filename
        patch_path.write_text(diff, encoding='utf-8')
        print(f"✓ Saved patch to: {patch_path}")
        print(f"  Patch preview:")
        print("  " + "\n  ".join(diff.split('\n')[:5]))

        # Extract target file
        target_file = extract_file_path_from_diff(diff)
        if target_file:
            print(f"  Target file: {target_file}")

        # Apply patch if requested
        if args.apply:
            print(f"Applying patch...")
            success, message = apply_patch(diff, patch_path)

            if success:
                print(f"✓ {message}")
                successful_patches.append({
                    'nodeid': nodeid,
                    'patch_file': str(patch_path),
                    'target_file': target_file,
                })
            else:
                print(f"✗ {message}")
                failed_patches.append({
                    'nodeid': nodeid,
                    'patch_file': str(patch_path),
                    'reason': message,
                })
        else:
            successful_patches.append({
                'nodeid': nodeid,
                'patch_file': str(patch_path),
                'target_file': target_file,
            })

    # Summary
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
            print(f"    Patch: {patch['patch_file']}")

    if failed_patches:
        print("\n✗ Failed patches:")
        for patch in failed_patches:
            print(f"  - {patch['nodeid']}")
            print(f"    Reason: {patch['reason']}")

    # Save summary as JSON for workflow to use
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
        print("  - The Gemini API couldn't generate valid patches")
        print("  - The patches couldn't be applied cleanly")
        print("  - There were API errors")
        # Exit 0 to allow workflow to continue and check for any partial changes
        sys.exit(0)


if __name__ == "__main__":
    main()
