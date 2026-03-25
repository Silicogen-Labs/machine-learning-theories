"""
RTL_E003 — Multiple drivers on the same signal.

A signal driven from more than one always block (or from both assign and
always) creates a contention — in synthesis this is usually an error; in
simulation it causes X or last-assignment-wins depending on the simulator.

Standard reference:
  • Verilator: MULTIDRIVEN
  • SpyGlass: W14
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import DefaultDict, List

from ..models import CheckID, Finding, Severity
from ..parser import ParsedFile


_RE_ASSIGN_LHS = re.compile(r"^\s*assign\s+(\w+)\b")
_RE_ALWAYS_LHS = re.compile(r"(\w+)\s*(?:\[.*?\])?\s*(?:<=|=)\s*(?!=)")
_KEYWORDS = frozenset({
    "if", "else", "case", "casez", "casex", "begin", "end",
    "for", "while", "repeat", "default", "assign", "endmodule",
    "module", "input", "output", "inout", "parameter", "localparam",
    "wire", "reg", "logic", "integer",
})


def check_multi_driver(pf: ParsedFile) -> List[Finding]:
    findings: List[Finding] = []

    # signal → list of (line_number, source_description)
    drivers: DefaultDict[str, List[tuple]] = defaultdict(list)

    # ── Continuous assignments (assign) ────────────────────────────────────
    for li in pf.iter_lines():
        m = _RE_ASSIGN_LHS.match(li.stripped)
        if m:
            sig = m.group(1)
            if sig not in _KEYWORDS:
                drivers[sig].append((li.number, "assign"))

    # ── Always block assignments ────────────────────────────────────────────
    for ab in pf.always_blocks:
        lines = pf.lines[ab.start_line - 1 : ab.end_line]
        for li in lines:
            for m in _RE_ALWAYS_LHS.finditer(li.stripped):
                sig = m.group(1)
                if sig not in _KEYWORDS and (sig.islower() or "_" in sig):
                    # Record block start line as the driver location
                    if not any(loc == ab.start_line for loc, _ in drivers.get(sig, [])):
                        drivers[sig].append((ab.start_line, f"always @line {ab.start_line}"))

    # ── Report signals with >1 driver ──────────────────────────────────────
    for sig, locs in drivers.items():
        if len(locs) > 1:
            lines_str = ", ".join(f"line {l}" for l, _ in locs)
            findings.append(Finding(
                check_id=CheckID.RTL_E003,
                severity=Severity.ERROR,
                message=(
                    f"Signal '{sig}' is driven from multiple sources ({lines_str}). "
                    "Multiple drivers cause contention — X in simulation, synthesis error."
                ),
                location=pf.location(locs[0][0]),
                fix_hint=(
                    f"Ensure '{sig}' is driven from exactly one always block or assign. "
                    "If multiple conditions need to drive it, use a priority mux or combine into one always block."
                ),
            ))

    return findings
