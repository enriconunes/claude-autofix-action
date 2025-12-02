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
    You are an automated code-repair agent. Analyze the failing test and return ONLY the corrected Python code.

    ### CRITICAL INSTRUCTIONS:
    1. Return ONLY the complete corrected Python file content
    2. Do NOT include explanations, descriptions, or markdown
    3. Do NOT include code fences (```)
    4. Start your response directly with the Python code
    5. Make MINIMAL changes - only fix what's broken
    6. PRESERVE ALL CODE - including if __name__ == "__main__" blocks, imports, comments, and everything else
    7. Do NOT remove or simplify any part of the original code
    8. Do NOT change variable names, function names, or parameter names
    9. Do NOT refactor or improve code that is not related to the bug
    10. Only change the EXACT line(s) that have the bug - nothing else
    11. If the bug is a wrong operator (like - instead of /), ONLY change that operator
    12. Keep absolutely everything else identical to the original file

    ### EXAMPLE:
    If the original file is:
    ```
    def my_function(a, b):
        return a - b  # BUG: should be addition

    if __name__ == "__main__":
        result = my_function(5, 3)
        print(result)
    ```

    Your output should be EXACTLY:
    def my_function(a, b):
        return a + b

    if __name__ == "__main__":
        result = my_function(5, 3)
        print(result)

    WRONG output (do NOT do this):
    def my_function(x, y):  # Changed parameter names - WRONG!
        return x + y

    WRONG output (do NOT do this):
    def my_function(a, b):
        return a + b  # Removed if __name__ block - WRONG!

    Now analyze the failing test and return the COMPLETE corrected Python file with ALL original code preserved and ONLY the bug fixed.
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


def extract_code_from_response(response_text: str) -> Optional[str]:
    """Extract Python code from Gemini's response."""

    # First, try to extract from markdown code fence
    code_pattern = r'```(?:python)?\s*\n(.*?)\n```'
    matches = re.findall(code_pattern, response_text, re.DOTALL | re.IGNORECASE)

    if matches:
        return matches[0].strip()

    # If no code fence, check if the response looks like Python code
    # (starts with common Python patterns)
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


def build_fix_payload(failure: Dict[str, Any], report: Dict[str, Any], index: int, source_file_path: Optional[str] = None) -> Dict[str, Any]:
    """Build a payload specifically for requesting fixes.

    Args:
        failure: The test failure information
        report: The full pytest report
        index: The failure index
        source_file_path: Optional path to the actual source file (not test file) to fix
    """

    # If we have a specific source file path, read it and include it
    if source_file_path:
        from gemini_report import read_source, format_longrepr

        source_code = read_source(source_file_path)
        longrepr = failure.get("longrepr")
        traceback_text = format_longrepr(longrepr)
        failure_json = json.dumps(failure, indent=2, ensure_ascii=False)

        # Build a custom prompt with the correct source file
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
            "contents": [
                {
                    "parts": [
                        {"text": body}
                    ]
                }
            ]
        }
    else:
        # Fallback to original behavior
        base_payload = build_payload(failure, report, index)
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

        # Get the source file path from the failure FIRST
        # This needs to happen before build_fix_payload so we can pass the correct file
        # Try to find the actual module being tested (not the test file)
        source_path = None

        # First, check if we can infer from nodeid
        # nodeid format: "test_module.py::test_function"
        nodeid_parts = nodeid.split("::")
        if nodeid_parts:
            test_file = nodeid_parts[0]
            # If it's a test file like "test_dividir.py", try to find "dividir.py"
            if test_file.startswith("test_") and test_file.endswith(".py"):
                potential_source = test_file.replace("test_", "", 1)

                # Try multiple locations for the source file
                search_paths = [
                    Path(potential_source),  # Same directory
                    Path.cwd() / potential_source,  # From working directory
                ]

                for search_path in search_paths:
                    if search_path.exists() and search_path.is_file():
                        source_path = str(search_path)
                        print(f"  Inferred source file from test name: {source_path}")
                        break

        # Fallback: try to extract from longrepr
        if not source_path:
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
                            break

            if not source_path:
                source_path = fallback_path

        if not source_path:
            print(f"⚠️  Could not determine source file path for {nodeid}")
            print(f"  Debug - nodeid: {nodeid}")
            print(f"  Debug - working directory: {Path.cwd()}")
            failed_patches.append({
                'nodeid': nodeid,
                'reason': 'Could not determine source file path',
            })
            continue

        # Convert to absolute path
        source_file = Path(source_path)
        if not source_file.is_absolute():
            source_file = (Path.cwd() / source_file).resolve()

        print(f"  Target file: {source_file}")

        # Now get fix from Gemini with the correct source file
        payload = build_fix_payload(failure, report, index, source_file_path=str(source_file))
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

        # Extract Python code from response
        fixed_code = extract_code_from_response(response_text)

        if not fixed_code:
            print(f"⚠️  No valid Python code found in Gemini response for {nodeid}")
            print(f"  Check {debug_file} for the full response")
            failed_patches.append({
                'nodeid': nodeid,
                'reason': 'No Python code in response',
                'debug_file': str(debug_file),
            })
            continue

        print(f"  Code preview:")
        print("  " + "\n  ".join(fixed_code.split('\n')[:5]))

        # Save the fixed code
        fixed_filename = f"{index:02d}_{source_file.name}"
        fixed_path = output_dir / fixed_filename
        fixed_path.write_text(fixed_code, encoding='utf-8')
        print(f"✓ Saved fixed code to: {fixed_path}")

        # Apply fix if requested
        if args.apply:
            print(f"Applying fix to {source_file}...")
            try:
                # Backup original file
                backup_path = source_file.with_suffix(source_file.suffix + '.backup')
                if source_file.exists():
                    import shutil
                    shutil.copy2(source_file, backup_path)
                    print(f"  Created backup: {backup_path}")

                # Write the fixed code
                source_file.write_text(fixed_code, encoding='utf-8')
                print(f"✓ Successfully applied fix to {source_file}")

                successful_patches.append({
                    'nodeid': nodeid,
                    'fixed_file': str(fixed_path),
                    'target_file': str(source_file),
                })
            except Exception as e:
                print(f"✗ Failed to apply fix: {e}")
                failed_patches.append({
                    'nodeid': nodeid,
                    'fixed_file': str(fixed_path),
                    'reason': f'Failed to write file: {e}',
                })
        else:
            successful_patches.append({
                'nodeid': nodeid,
                'fixed_file': str(fixed_path),
                'target_file': str(source_file),
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
            print(f"    Patch: {patch['fixed_file']}")

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
