"""
RTL_W003 — Incomplete sensitivity list.

A sensitivity list that is missing signals used on the RHS of assignments
causes simulation to produce different results than synthesis (synthesised
hardware is always combinational — it responds to every input change).

Standard reference:
  • Verilator: UNOPTFLAT (for loops), plus style warnings
  • SpyGlass: W28
  • IEEE 1800-2017: always_comb automatically infers the full list; use it.

This check only fires on legacy `always @(explicit_list)` blocks, not on
`always_comb` or `always @(*)` which are always complete by definition.

Algorithm:
  1. Extract signals listed in the sensitivity list.
  2. Extract all identifiers on the RHS of assignments in the block.
  3. Any RHS signal not in the sensitivity list is a missing entry.
"""

from __future__ import annotations

import re
from typing import List, Set

from ..models import CheckID, Finding, Severity
from ..parser import ParsedFile, AlwaysKind


_RE_SENS_SIG = re.compile(r"\b(?:posedge|negedge|edge)?\s*(\w+)")
_KEYWORDS = frozenset({
    "posedge", "negedge", "edge", "or", "and", "if", "else",
    "begin", "end", "case", "casez", "casex", "endcase",
    "default", "for", "while", "repeat", "integer",
})


def _extract_sens_signals(sens_text: str) -> Set[str]:
    sigs: Set[str] = set()
    for m in _RE_SENS_SIG.finditer(sens_text):
        name = m.group(1)
        if name not in _KEYWORDS and not name.isdigit():
            sigs.add(name)
    return sigs


def _extract_rhs_signals(block_lines: list) -> Set[str]:
    sigs: Set[str] = set()
    for li in block_lines:
        s = li.stripped
        # Grab everything after = / <=
        for rhs in re.findall(r"(?:<?)=\s*(.+)", s):
            for name in re.findall(r"\b([a-zA-Z_]\w*)\b", rhs):
                if name not in _KEYWORDS and not name.isdigit():
                    sigs.add(name)
        # Also grab condition expressions in if/case
        for cond in re.findall(r"\bif\s*\(([^)]+)\)", s):
            for name in re.findall(r"\b([a-zA-Z_]\w*)\b", cond):
                if name not in _KEYWORDS:
                    sigs.add(name)
    return sigs


def check_sensitivity_list(pf: ParsedFile) -> List[Finding]:
    findings: List[Finding] = []

    for ab in pf.always_blocks:
        # Only check explicit sensitivity lists (not always_comb / always @(*))
        if ab.kind in (AlwaysKind.COMB, AlwaysKind.FF):
            continue  # always_comb is complete by construction
        if not ab.sensitivity or "*" in ab.sensitivity:
            continue  # @(*) is complete

        # Skip clocked blocks — missing clock edges are handled elsewhere
        if ab.has_posedge or ab.has_negedge:
            continue

        sens_sigs = _extract_sens_signals(ab.sensitivity)
        lines = pf.lines[ab.start_line - 1 : ab.end_line]
        rhs_sigs = _extract_rhs_signals(lines)

        missing = rhs_sigs - sens_sigs - {"1", "0"}
        # Filter out likely constants, parameters, module names (heuristic)
        missing = {s for s in missing if s[0].islower() or s[0] == "_"}

        if missing:
            findings.append(Finding(
                check_id=CheckID.RTL_W003,
                severity=Severity.WARNING,
                message=(
                    f"Incomplete sensitivity list: signals {sorted(missing)} are used "
                    f"in the block but missing from @({ab.sensitivity.strip()}). "
                    "Simulation will not re-evaluate when these signals change."
                ),
                location=pf.location(ab.start_line),
                fix_hint=(
                    "Replace explicit sensitivity list with always_comb or always @(*) "
                    "to let the tool infer the complete list automatically."
                ),
            ))

    return findings
