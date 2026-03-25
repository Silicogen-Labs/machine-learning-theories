"""
RTL_E005 — Non-blocking assignment (<=) in combinational always block.

Standard reference:
  • IEEE 1800-2017 §9.4.2
  • Verilator: BLKANDNBLK
  • SpyGlass: W416a

Non-blocking assignments in always_comb / always @(*) will:
  1. Cause a delta-cycle simulation loop (Verilator emits error).
  2. Produce latches or undefined behaviour post-synthesis.
"""

from __future__ import annotations

import re
from typing import List

from ..models import CheckID, Finding, Severity
from ..parser import ParsedFile, AlwaysKind


def check_nonblocking_in_comb(pf: ParsedFile) -> List[Finding]:
    findings: List[Finding] = []

    for ab in pf.always_blocks:
        if ab.kind not in (AlwaysKind.COMB,):
            continue

        lines = pf.lines[ab.start_line - 1 : ab.end_line]
        for li in lines:
            s = li.stripped
            if not s:
                continue
            # Skip declarations
            if re.match(r"\b(?:wire|reg|logic|integer|int|bit|byte|real)\b", s):
                continue
            if "<=" in s:
                # Exclude comparison context: if (a <= b)
                # Heuristic: preceded by ( or a comparison keyword
                clean = re.sub(r"\(.*?<=.*?\)", "()", s)  # remove parens first
                if "<=" in clean:
                    findings.append(Finding(
                        check_id=CheckID.RTL_E005,
                        severity=Severity.ERROR,
                        message=(
                            "Non-blocking assignment '<=' in combinational always block. "
                            "Use blocking '=' for combinational logic; '<=' causes a "
                            "simulation delta-cycle loop and synthesis latch."
                        ),
                        location=pf.location(li.number),
                        fix_hint="Replace '<=' with '=' in combinational blocks.",
                    ))

    return findings
