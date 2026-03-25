"""
Data models shared across the entire rtl_analyzer package.

All checks produce Finding objects.  The rest of the codebase works
exclusively with these typed structures — no raw dicts, no stringly-typed
magic values.
"""

from __future__ import annotations

import dataclasses
import enum
from pathlib import Path
from typing import Optional


class Severity(str, enum.Enum):
    """
    Severity mirrors the levels used by Synopsys SpyGlass and Cadence HAL
    so output can be compared apples-to-apples with commercial tools.

    ERROR   — will almost certainly cause a silicon or functional bug.
    WARNING — probable bug; rare false-positive rate (<5% on real RTL).
    INFO    — coding style violation correlated with bugs; never a sole
              reason to block tape-out but should be addressed.
    """

    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


class CheckID(str, enum.Enum):
    """
    Every check has a stable, versioned ID so users can suppress specific
    checks in CI (e.g.  --suppress RTL_W002) without breaking future runs.

    Naming convention:
        RTL_E  — deterministic errors (latch, comb-loop, …)
        RTL_W  — deterministic warnings (width mismatch, blocking/NB, …)
        RTL_I  — informational / style
    """

    # ── Errors ──────────────────────────────────────────────────────────────
    RTL_E001 = "RTL_E001"   # Unintended latch inference
    RTL_E002 = "RTL_E002"   # Combinational loop
    RTL_E003 = "RTL_E003"   # Multiple drivers on the same signal
    RTL_E004 = "RTL_E004"   # Blocking assignment in sequential always block
    RTL_E005 = "RTL_E005"   # Non-blocking assignment in combinational always block
    RTL_E006 = "RTL_E006"   # FSM: unreachable state detected

    # ── Warnings ────────────────────────────────────────────────────────────
    RTL_W001 = "RTL_W001"   # Missing default in case statement
    RTL_W002 = "RTL_W002"   # Width mismatch (truncation / extension)
    RTL_W003 = "RTL_W003"   # Incomplete sensitivity list
    RTL_W004 = "RTL_W004"   # Missing reset on state register
    RTL_W005 = "RTL_W005"   # Simulation-synthesis mismatch risk (initial/delay)
    RTL_W006 = "RTL_W006"   # FSM: missing default in next-state logic
    RTL_W007 = "RTL_W007"   # CDC: signal crosses clock domains without synchroniser

    # ── Informational ───────────────────────────────────────────────────────
    RTL_I001 = "RTL_I001"   # Unused signal / port
    RTL_I002 = "RTL_I002"   # Signal declared but never driven
    RTL_I003 = "RTL_I003"   # Empty always block

    # ── Phase 3 ML contracts ────────────────────────────────────────────────
    RTL_ML001 = "RTL_ML001"
    RTL_ML002 = "RTL_ML002"
    RTL_ML003 = "RTL_ML003"


@dataclasses.dataclass(frozen=True)
class Location:
    """Source location of a finding."""
    file: Path
    line: int
    column: Optional[int] = None

    def __str__(self) -> str:
        col = f":{self.column}" if self.column is not None else ""
        return f"{self.file}:{self.line}{col}"


@dataclasses.dataclass(frozen=True)
class Finding:
    """
    A single bug / warning / info item produced by a check.

    Designed to be serialisable to JSON for CI integration and comparable
    against Verilator / Verible / SpyGlass output for benchmarking.
    """

    check_id: CheckID
    severity: Severity
    message: str
    location: Location
    fix_hint: str = ""
    # Which analyser produced this (for multi-tool comparison)
    source: str = "rtl_analyzer"
    confidence: Optional[float] = None
    metadata: dict = dataclasses.field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "check_id": self.check_id.value,
            "severity": self.severity.value,
            "message": self.message,
            "file": str(self.location.file),
            "line": self.location.line,
            "column": self.location.column,
            "fix_hint": self.fix_hint,
            "source": self.source,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }

    def __str__(self) -> str:
        loc = str(self.location)
        return f"[{self.severity.value}] {self.check_id.value}  {loc}  {self.message}"
