"""Abstract base class for test framework adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class TestAdapter(ABC):
    """Common interface for all test framework adapters.

    Each adapter knows how to:
    - Parse the framework's JSON report format
    - Extract normalised failure dicts
    - Format a failure for display / prompt building
    - Infer the source file that should be fixed from a failure
    """

    @abstractmethod
    def parse_report(self, path: str) -> Dict[str, Any]:
        """Load the test report file and return its parsed content."""
        ...

    @abstractmethod
    def extract_failures(self, report: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Return a list of normalised failure dicts from the report."""
        ...

    @abstractmethod
    def format_failure(self, failure: Dict[str, Any]) -> str:
        """Format a failure dict into a human-readable traceback/error string."""
        ...

    @abstractmethod
    def infer_source_file(self, failure: Dict[str, Any]) -> Optional[str]:
        """Infer the path of the source file to fix from a failure dict."""
        ...

    @abstractmethod
    def get_language(self) -> str:
        """Return the human-readable language name used in prompts (e.g. 'Python')."""
        ...

    @abstractmethod
    def get_extension(self) -> str:
        """Return the primary file extension for this language (e.g. '.py')."""
        ...
