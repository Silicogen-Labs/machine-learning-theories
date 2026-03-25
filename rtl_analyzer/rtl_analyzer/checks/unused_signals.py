"""
RTL_I001 — Unused signals and ports.
RTL_I002 — Declared signal never driven.

Unused signals waste area in synthesis and clutter code review.
Undriven signals are always X in simulation and float in hardware.

Standard reference:
  • Verilator: UNUSED, UNDRIVEN
  • Verible: no direct equivalent
  • SpyGlass: W240 (unused), W01 (undriven)

Scope: intra-module analysis only.  Cross-module (hierarchical)
analysis requires elaboration and is deferred to Phase 2.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import DefaultDict, List, Set

from ..models import CheckID, Finding, Severity
from ..parser import ParsedFile


_KEYWORDS = frozenset({
    "module", "endmodule", "input", "output", "inout", "wire", "reg",
    "logic", "integer", "int", "bit", "byte", "real", "parameter",
    "localparam", "assign", "always", "initial", "begin", "end",
    "if", "else", "case", "casez", "casex", "endcase", "for",
    "while", "repeat", "default", "posedge", "negedge",
})

_RE_DECL = re.compile(
    r"\b(?:wire|reg|logic|bit)\b\s*(?:signed|unsigned)?\s*"
    r"(?:\[.*?\]\s*)?"
    r"(\w+)\s*[,;()\n]"
)
_RE_PORT = re.compile(
    r"\b(?:input|output|inout)\b\s*(?:wire|reg|logic)?\s*"
    r"(?:signed|unsigned)?\s*(?:\[.*?\]\s*)?(\w+)"
)
_RE_IDENT = re.compile(r"\b([a-zA-Z_]\w*)\b")
_RE_ASSIGN_LHS = re.compile(r"^\s*assign\s+(\w+)\b")
_RE_ALWAYS_LHS = re.compile(r"(\w+)\s*(?:\[.*?\])?\s*(?:<=|=)\s*(?!=)")
# Matches sensitivity list contents: @(posedge clk or negedge rst_n) or @(a or b)
_RE_SENSITIVITY = re.compile(r"@\s*\(([^)]+)\)")


def check_unused_signals(pf: ParsedFile) -> List[Finding]:
    findings: List[Finding] = []

    declared: dict[str, int] = {}   # name → line number of declaration
    driven: Set[str] = set()        # signals with a driver
    used: Set[str] = set()          # signals read on RHS or in conditions

    # ── Collect declarations ────────────────────────────────────────────────
    for li in pf.iter_lines():
        s = li.stripped
        for m in _RE_DECL.finditer(s):
            name = m.group(1)
            if name not in _KEYWORDS:
                declared[name] = li.number
        for m in _RE_PORT.finditer(s):
            name = m.group(1)
            if name not in _KEYWORDS:
                declared[name] = li.number
                # Inputs are implicitly "driven" from outside
                if s.startswith("input"):
                    driven.add(name)

    # ── Collect drivers ─────────────────────────────────────────────────────
    for li in pf.iter_lines():
        s = li.stripped
        m = _RE_ASSIGN_LHS.match(s)
        if m:
            driven.add(m.group(1))
        for m in _RE_ALWAYS_LHS.finditer(s):
            driven.add(m.group(1))

    # ── Collect uses (RHS and conditions) ───────────────────────────────────
    for li in pf.iter_lines():
        s = li.stripped
        # RHS of assignments
        for rhs in re.findall(r"(?:<?)=\s*(.+)", s):
            for name in _RE_IDENT.findall(rhs):
                used.add(name)
        # Conditions
        for cond in re.findall(r"\bif\s*\(([^)]+)\)|\bcase[xz]?\s*\(([^)]+)\)", s):
            for part in cond:
                for name in _RE_IDENT.findall(part):
                    used.add(name)
        # Port connections in instantiations: .port(signal)
        for name in re.findall(r"\.\w+\s*\(\s*(\w+)\s*\)", s):
            used.add(name)
        # Sensitivity lists: @(posedge clk or negedge rst_n)
        for sens_m in _RE_SENSITIVITY.finditer(s):
            for name in _RE_IDENT.findall(sens_m.group(1)):
                if name not in {"posedge", "negedge", "edge", "or", "and"}:
                    used.add(name)

    # ── Report ──────────────────────────────────────────────────────────────
    for name, lineno in declared.items():
        if name in _KEYWORDS or name.startswith("_"):
            continue
        if name not in used and name not in driven:
            # Truly dead signal: never read AND never written
            findings.append(Finding(
                check_id=CheckID.RTL_I001,
                severity=Severity.INFO,
                message=f"Signal '{name}' is declared but never used in this module.",
                location=pf.location(lineno),
                fix_hint=f"Remove '{name}' if unused, or prefix with '_' to suppress this check.",
            ))
        elif name in used and name not in driven and not name.startswith("input"):
            # Signal is read but has no driver — always X
            findings.append(Finding(
                check_id=CheckID.RTL_I002,
                severity=Severity.INFO,
                message=f"Signal '{name}' is used but never explicitly driven in this module.",
                location=pf.location(lineno),
                fix_hint=f"Ensure '{name}' has a driver (assign or always block).",
            ))

    return findings
