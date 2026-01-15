"""Pytest JSON report parsing."""

from __future__ import annotations

import json
import sys
from typing import Any, Dict, List


def load_report(path: str) -> Dict[str, Any]:
    """Load pytest JSON report from file."""
    try:
        with open(path, "r", encoding="utf-8") as report_file:
            return json.load(report_file)
    except FileNotFoundError as exc:
        print(f"Pytest JSON report not found at {path}: {exc}", file=sys.stderr)
        raise SystemExit(1)


def extract_failures(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract all failed tests from pytest report."""
    return [test for test in report.get("tests", []) if test.get("outcome") == "failed"]
