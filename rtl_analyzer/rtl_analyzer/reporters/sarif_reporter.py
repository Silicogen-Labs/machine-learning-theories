"""
SARIF v2.1.0 reporter.

SARIF (Static Analysis Results Interchange Format) is the standard used by
GitHub Code Scanning, VS Code SARIF Viewer, and Azure DevOps.
Producing SARIF means our findings can be surfaced natively in PRs.

Spec: https://docs.oasis-open.org/sarif/sarif/v2.1.0/
"""

from __future__ import annotations

import json
import sys
from typing import IO

from ..engine import AnalysisResult
from ..models import Severity

_LEVEL_MAP = {
    Severity.ERROR:   "error",
    Severity.WARNING: "warning",
    Severity.INFO:    "note",
}


class SarifReporter:
    TOOL_NAME = "rtl-analyzer"
    TOOL_VERSION = "0.1.0"
    TOOL_URL = "https://github.com/silicogen/rtl-analyzer"

    def __init__(self, stream: IO = None):
        self._stream = stream or sys.stdout

    def report(self, result: AnalysisResult) -> None:
        rules = {}
        results = []

        for f in result.all_findings:
            rid = f.check_id.value
            if rid not in rules:
                rules[rid] = {
                    "id": rid,
                    "shortDescription": {"text": f.message[:80]},
                    "helpUri": f"{self.TOOL_URL}/checks#{rid.lower()}",
                    "defaultConfiguration": {"level": _LEVEL_MAP[f.severity]},
                }
            results.append({
                "ruleId": rid,
                "level": _LEVEL_MAP[f.severity],
                "message": {"text": f.message},
                "locations": [{
                    "physicalLocation": {
                        "artifactLocation": {"uri": str(f.location.file)},
                        "region": {
                            "startLine": f.location.line,
                            **({"startColumn": f.location.column}
                               if f.location.column else {}),
                        },
                    },
                }],
                **({"fixes": [{"description": {"text": f.fix_hint}}]} if f.fix_hint else {}),
            })

        sarif = {
            "$schema": "https://schemastore.azurewebsites.net/schemas/json/sarif-2.1.0-rtm.5.json",
            "version": "2.1.0",
            "runs": [{
                "tool": {
                    "driver": {
                        "name": self.TOOL_NAME,
                        "version": self.TOOL_VERSION,
                        "informationUri": self.TOOL_URL,
                        "rules": list(rules.values()),
                    }
                },
                "results": results,
            }],
        }

        json.dump(sarif, self._stream, indent=2)
        self._stream.write("\n")
