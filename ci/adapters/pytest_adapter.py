"""Pytest adapter — wraps the existing ci/pytest/ and ci/fix/ modules."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure the ci/ directory is on the path when this module is imported standalone
sys.path.insert(0, str(Path(__file__).parent.parent))

from adapters.base import TestAdapter
from pytest.parser import load_report, extract_failures
from pytest.formatter import format_longrepr
from fix.inference import infer_source_file


class PytestAdapter(TestAdapter):
    """Adapter for Python/pytest projects."""

    def parse_report(self, path: str) -> Dict[str, Any]:
        return load_report(path)

    def extract_failures(self, report: Dict[str, Any]) -> List[Dict[str, Any]]:
        return extract_failures(report)

    def format_failure(self, failure: Dict[str, Any]) -> str:
        return format_longrepr(failure.get("longrepr"))

    def infer_source_file(self, failure: Dict[str, Any]) -> Optional[str]:
        return infer_source_file(failure)

    def get_language(self) -> str:
        return "Python"

    def get_extension(self) -> str:
        return ".py"
