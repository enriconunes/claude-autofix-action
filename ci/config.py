"""Configuration and constants for Claude CI."""

import textwrap

# API Configuration
API_BASE_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

# Model selection — edit these two constants to change the model for each step.
# Available options (Anthropic model IDs):
#   Sonnet 4.5 : claude-sonnet-4-5-20250929  (smartest, higher cost)
#   Haiku  3.5 : claude-3-5-haiku-20241022   (fastest,  lower  cost)
COMMENT_CLAUDE_MODEL = "claude-3-5-haiku-20241022"  # used by claude_report.py (PR comment)
FIX_CLAUDE_MODEL     = "claude-sonnet-4-5-20250929"  # used by claude_fix.py    (code fix)

FALLBACK_MODELS = ["claude-sonnet-4-20250514", "claude-3-5-sonnet-20241022"]

# ── Error log settings ────────────────────────────────────────────────────────
# Set to True to append a JSONL entry to logs/error_history.jsonl (in main) for
# every failing test. Does NOT consume Claude API tokens — pure data collection.
ENABLE_ERROR_LOG = False

# Set to True to post a Claude-powered insight comment on the PR based on the
# author's error history. Requires ENABLE_ERROR_LOG on previous runs to have data.
# Uses Claude Haiku — low token cost. Needs at least 3 entries for the same author.
ENABLE_INSIGHTS = False

# ── Test generation settings ──────────────────────────────────────────────────
# Set to True to automatically generate tests for new source files in PRs (trigger B).
AUTO_GENERATE_TESTS_ON_PR     = False

# Framework and language used when the PR trigger fires (trigger B).
# For the manual trigger (workflow_dispatch) these are passed as inputs instead.
AUTO_GENERATE_TESTS_FRAMEWORK = "pytest"                    # pytest | vitest | jest
AUTO_GENERATE_TESTS_LANGUAGE  = "python"                    # python | typescript | javascript

# Model used for test generation (can differ from fix/comment models).
GENERATE_TESTS_CLAUDE_MODEL   = "claude-sonnet-4-5-20250929"

# Analysis prompt — language-agnostic (format is the same for any language)
BASE_ANALYSIS_PROMPT = textwrap.dedent(
    """
    You are a CI code-repair agent. Analyse the failing test and respond in this exact format — nothing more:

    **File:** `<file>` | **Line:** <line>
    **Error:** expected `<expected>`, got `<actual>`
    **Cause:** <one sentence describing the bug>
    **Fix:** change `<wrong code>` to `<correct code>`

    Rules:
    - Maximum 4 lines of output.
    - No sections, no headers, no diff, no PR guidance.
    - Be direct and specific. Reference exact values from the traceback.
    """
)


def get_generate_tests_prompt(language: str = "Python", framework: str = "pytest") -> str:
    """Return the prompt used to generate tests for a source file."""
    return textwrap.dedent(
        f"""
        You are an expert {language} developer and testing specialist.
        Generate a comprehensive test file for the provided source code using {framework}.

        ### CRITICAL INSTRUCTIONS:
        1. Return ONLY the complete test file content — no explanations, no markdown
        2. Do NOT include code fences (```)
        3. Start your response directly with the first import or test
        4. Cover: normal cases, edge cases, boundary values, and error/exception cases
        5. Each test function tests ONE specific behaviour with a descriptive name
        6. Do NOT test private functions (prefixed with _ in Python, or not exported in JS/TS)
        7. Make tests completely independent — no shared mutable state between tests
        8. Use the correct import path based on the relative location shown in "Output file path"
        9. Do not add tests that always pass trivially (e.g. assert True)
        """
    )


def get_fix_prompt(language: str = "Python", extension: str = ".py") -> str:
    """Return the fix prompt parametrised for the given language.

    Args:
        language:  Human-readable language name, e.g. "Python", "TypeScript", "JavaScript".
        extension: Primary file extension, e.g. ".py", ".ts", ".js".
    """
    return textwrap.dedent(
        f"""
        You are an automated code-repair agent. Analyze the failing test and return ONLY the corrected {language} code.

        ### CRITICAL INSTRUCTIONS:
        1. Return ONLY the complete corrected {language} file content
        2. Do NOT include explanations, descriptions, or markdown
        3. Do NOT include code fences (```)
        4. Start your response directly with the {language} code
        5. Make MINIMAL changes - only fix what's broken
        6. PRESERVE ALL CODE - including imports, exports, comments, and everything else
        7. Do NOT remove or simplify any part of the original code
        8. Do NOT change variable names, function names, or parameter names
        9. Do NOT refactor or improve code that is not related to the bug
        10. Only change the EXACT line(s) that have the bug - nothing else
        11. If the bug is a wrong operator (like - instead of /), ONLY change that operator
        12. Keep absolutely everything else identical to the original file

        Now analyze the failing test and return the COMPLETE corrected {language} file with ALL original code preserved and ONLY the bug fixed.
        """
    )


# Keep FIX_PROMPT as a backwards-compatible alias for Python (pytest) usage
FIX_PROMPT = get_fix_prompt("Python", ".py")
