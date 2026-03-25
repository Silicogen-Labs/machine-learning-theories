"""
Analysis engine — orchestrates parsing and all checks for one or more files.

Designed for use both as a library (from Python) and via the CLI.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

from .checks import ALL_CHECKS
from .models import CheckID, Finding, Severity
from .parser import parse_file, ParsedFile


@dataclass
class FileResult:
    path: Path
    parsed: ParsedFile
    findings: List[Finding] = field(default_factory=list)
    elapsed_ms: float = 0.0

    @property
    def errors(self) -> List[Finding]:
        return [f for f in self.findings if f.severity == Severity.ERROR]

    @property
    def warnings(self) -> List[Finding]:
        return [f for f in self.findings if f.severity == Severity.WARNING]

    @property
    def infos(self) -> List[Finding]:
        return [f for f in self.findings if f.severity == Severity.INFO]


@dataclass
class AnalysisResult:
    file_results: List[FileResult] = field(default_factory=list)
    total_elapsed_ms: float = 0.0

    @property
    def all_findings(self) -> List[Finding]:
        return [f for fr in self.file_results for f in fr.findings]

    @property
    def error_count(self) -> int:
        return sum(len(fr.errors) for fr in self.file_results)

    @property
    def warning_count(self) -> int:
        return sum(len(fr.warnings) for fr in self.file_results)

    @property
    def info_count(self) -> int:
        return sum(len(fr.infos) for fr in self.file_results)

    def to_dict(self) -> dict:
        return {
            "summary": {
                "files": len(self.file_results),
                "errors": self.error_count,
                "warnings": self.warning_count,
                "infos": self.info_count,
                "total_elapsed_ms": round(self.total_elapsed_ms, 2),
            },
            "findings": [f.to_dict() for f in self.all_findings],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


class AnalysisEngine:
    """
    General-purpose RTL analysis engine.

    Usage:
        engine = AnalysisEngine()
        result = engine.analyze_files([Path("foo.v"), Path("bar.sv")])

    Suppression:
        engine = AnalysisEngine(suppress={CheckID.RTL_I001})
    """

    def __init__(
        self,
        checks: Optional[List[Callable]] = None,
        suppress: Optional[set] = None,
        severity_filter: Optional[set] = None,
        phase3_enabled: bool = False,
        enabled_ml_checks: Optional[set[str]] = None,
        model_dir: Optional[Path] = None,
    ):
        self._checks = checks if checks is not None else ALL_CHECKS
        self._suppress = suppress or set()
        self._severity_filter = severity_filter  # None = all
        self._phase3_enabled = phase3_enabled
        self._enabled_ml_checks = self._normalize_ml_checks(enabled_ml_checks)
        self._model_dir = model_dir

    @staticmethod
    def _normalize_ml_checks(enabled_ml_checks: Optional[set[str]]) -> Optional[frozenset[str]]:
        if enabled_ml_checks is None:
            return None
        return frozenset(
            token.strip().lower()
            for token in enabled_ml_checks
            if token.strip()
        )

    def analyze_file(self, path: Path) -> FileResult:
        t0 = time.perf_counter()
        pf = parse_file(path)
        findings: List[Finding] = []

        # Surface pyslang parse errors as WARNING findings so they are never silently dropped
        for err in pf.parse_errors:
            findings.append(Finding(
                check_id=CheckID.RTL_W005,   # closest existing ID; parse error = sim/synth risk
                severity=Severity.WARNING,
                message=f"Parse error (pyslang): {err}",
                location=pf.location(1),
                fix_hint="Fix the syntax error reported above before relying on analysis results.",
                source="pyslang",
            ))

        for check in self._checks:
            try:
                new = check(pf)
                findings.extend(new)
            except Exception as exc:
                # Never let a buggy check crash the whole run
                findings.append(Finding(
                    check_id=CheckID.RTL_E001,  # placeholder
                    severity=Severity.INFO,
                    message=f"[internal] Check {check.__name__} raised: {exc}",
                    location=pf.location(1),
                    source="rtl_analyzer/internal",
                ))

        # Apply suppression and filter
        findings = [
            f for f in findings
            if f.check_id not in self._suppress
            and (self._severity_filter is None or f.severity in self._severity_filter)
        ]

        # Sort by line number
        findings.sort(key=lambda f: (f.location.line, f.check_id.value))

        elapsed = (time.perf_counter() - t0) * 1000
        return FileResult(path=path, parsed=pf, findings=findings, elapsed_ms=elapsed)

    def analyze_files(self, paths: List[Path]) -> AnalysisResult:
        t0 = time.perf_counter()
        result = AnalysisResult()
        for path in paths:
            fr = self.analyze_file(path)
            result.file_results.append(fr)
        result.total_elapsed_ms = (time.perf_counter() - t0) * 1000
        return result

    def analyze_directory(
        self,
        directory: Path,
        glob: str = "**/*.{v,sv}",
        recursive: bool = True,
    ) -> AnalysisResult:
        pattern_v = "**/*.v" if recursive else "*.v"
        pattern_sv = "**/*.sv" if recursive else "*.sv"
        files = sorted(
            list(directory.glob(pattern_v)) + list(directory.glob(pattern_sv))
        )
        return self.analyze_files(files)
