"""JSON reporter — outputs AnalysisResult as structured JSON."""

from __future__ import annotations

import sys
from typing import IO

from ..engine import AnalysisResult


class JsonReporter:
    def __init__(self, stream: IO = None, indent: int = 2):
        self._stream = stream or sys.stdout
        self._indent = indent

    def report(self, result: AnalysisResult) -> None:
        self._stream.write(result.to_json(indent=self._indent))
        self._stream.write("\n")
