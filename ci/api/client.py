"""Claude API client for sending requests."""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from ..config import API_BASE_URL, ANTHROPIC_VERSION, DEFAULT_CLAUDE_MODEL
from .models import iter_candidate_models, resolve_model_name


def send_to_claude(api_key: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Send request to Claude API with retry logic."""
    errors: List[str] = []
    model_name = payload.get("model", DEFAULT_CLAUDE_MODEL)

    for current_model in iter_candidate_models(model_name):
        # Update payload with current model
        current_payload = payload.copy()
        current_payload["model"] = current_model

        print(f"Attempting Claude request using model: {current_model}")

        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
        }

        request = urllib.request.Request(
            API_BASE_URL,
            data=json.dumps(current_payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            error_detail = exc.read().decode("utf-8", errors="replace")
            message = (
                f"Claude API request failed with model {current_model}: "
                f"{exc.code} {exc.reason}\n{error_detail}"
            )
            print(message, file=sys.stderr)

            # 529 means overloaded, worth retrying
            if exc.code == 529:
                print("Model overloaded, waiting before retry...", file=sys.stderr)
                time.sleep(2)
                # Retry once for overloaded
                try:
                    request = urllib.request.Request(
                        API_BASE_URL,
                        data=json.dumps(current_payload).encode("utf-8"),
                        headers=headers,
                        method="POST",
                    )
                    with urllib.request.urlopen(request, timeout=120) as response:
                        return json.load(response)
                except Exception as retry_exc:
                    print(f"Retry failed: {retry_exc}", file=sys.stderr)

            errors.append(message)
        except urllib.error.URLError as exc:
            message = f"Failed to reach Claude API with model {current_model}: {exc}"
            print(message, file=sys.stderr)
            errors.append(message)
        except Exception as exc:
            message = f"Unexpected error with model {current_model}: {exc}"
            print(message, file=sys.stderr)
            errors.append(message)

    print("All Claude API attempts failed.", file=sys.stderr)
    if errors:
        print("\nErrors encountered:", file=sys.stderr)
        for error in errors[:3]:  # Show first 3 errors
            print(f"  - {error}", file=sys.stderr)
    raise SystemExit(1)


def send_health_check(api_key: str, model_name: Optional[str] = None) -> None:
    """Send a minimal prompt to verify Claude connectivity."""
    resolved_model = model_name or resolve_model_name()

    payload = {
        "model": resolved_model,
        "max_tokens": 10,
        "messages": [
            {
                "role": "user",
                "content": "1+1. Answer with only one number, nothing more.",
            }
        ]
    }

    print(
        f"No failing tests were captured. Sending Claude health check prompt using "
        f"model '{resolved_model}'..."
    )
    response = send_to_claude(api_key, payload)
    print("Claude health check response:")
    print(json.dumps(response, indent=2, ensure_ascii=False))
