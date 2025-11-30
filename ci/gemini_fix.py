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
    You are an automated code-repair agent. Your task is to fix Python code based on test failures.

    ### IMPORTANT INSTRUCTIONS:
    1. Analyze the failing test and the source code provided
    2. Identify the root cause of the failure
    3. Generate a MINIMAL fix that addresses ONLY the failing test
    4. Output the fix as a valid unified diff format that can be applied with `git apply`

    ### REQUIRED OUTPUT FORMAT:
    You MUST provide your response in this exact structure:

    **Root Cause:**
    [Brief explanation of why the test failed]

    **Fix Description:**
    [Brief explanation of what the fix does]

    **Diff:**
    ```diff
    --- a/path/to/file.py
    +++ b/path/to/file.py
    @@ -line,count +line,count @@
     context line
    -removed line
    +added line
     context line
    ```

    ### CRITICAL RULES:
    - The diff MUST be in valid unified diff format
    - The diff MUST use paths relative to repository root (e.g., `src/module.py` not `/full/path/to/src/module.py`)
    - The diff MUST be minimal - only fix what's broken
    - Do NOT include explanations inside the diff block
    - Do NOT rewrite entire functions unless absolutely necessary
    - Do NOT add features or refactor unrelated code
    - The patch MUST apply cleanly with `git apply` or `patch` command

    Now analyze the test failure and provide the fix.
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

    # Look for diff block in markdown code fence
    diff_pattern = r'```diff\s*\n(.*?)\n```'
    matches = re.findall(diff_pattern, response_text, re.DOTALL | re.IGNORECASE)

    if matches:
        # Return the first diff found
        return matches[0].strip()

    # Fallback: look for anything that looks like a unified diff
    lines = response_text.split('\n')
    diff_lines = []
    in_diff = False

    for line in lines:
        if line.startswith('---') or line.startswith('+++'):
            in_diff = True

        if in_diff:
            diff_lines.append(line)

            # Stop if we hit a line that doesn't look like diff
            if diff_lines and not any(
                line.startswith(prefix)
                for prefix in ['---', '+++', '@@', '-', '+', ' ', '\\']
            ) and line.strip():
                break

    if diff_lines:
        return '\n'.join(diff_lines).strip()

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

        # Extract diff
        diff = extract_diff_from_response(response_text)

        if not diff:
            print(f"⚠️  No valid diff found in Gemini response for {nodeid}")
            failed_patches.append({
                'nodeid': nodeid,
                'reason': 'No diff in response',
            })
            continue

        # Validate diff
        is_valid, validation_msg = validate_diff(diff)
        if not is_valid:
            print(f"⚠️  Invalid diff format: {validation_msg}")
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

    # Exit with error if no patches were successful
    if not successful_patches:
        print("\n⚠️  No patches were successfully generated/applied.")
        sys.exit(1)


if __name__ == "__main__":
    main()
