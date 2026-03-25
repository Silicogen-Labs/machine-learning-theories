"""
reporters/__init__.py — output formatters for AnalysisResult.

Each reporter takes an AnalysisResult and produces output in a specific
format.  All reporters are pure functions (no side effects beyond writing
to the provided stream).

Supported formats:
  • text  — human-readable, colour via rich
  • json  — machine-readable, for CI integration
  • sarif — Static Analysis Results Interchange Format (GitHub / VSCode)
"""

from .text_reporter import TextReporter
from .json_reporter import JsonReporter
from .sarif_reporter import SarifReporter

__all__ = ["TextReporter", "JsonReporter", "SarifReporter"]
