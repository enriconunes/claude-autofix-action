"""Configuration and constants for Claude CI."""

import textwrap

# API Configuration
API_BASE_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_CLAUDE_MODEL = "claude-sonnet-4-5-20250929"  # Sonnet 4.5
FALLBACK_MODELS = ["claude-sonnet-4-20250514", "claude-3-5-sonnet-20241022"]

# Prompts
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
