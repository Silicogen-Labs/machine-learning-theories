"""
RTL_E004 — Blocking assignment (=) in sequential (always_ff / clocked) block.

Standard reference:
  • IEEE 1800-2017 §9.4.2: "In a sequential logic description, only
    nonblocking assignments should be used to assign values to variables."
  • Verilator: BLKSEQ
  • SpyGlass: W415a

False-positive handling:
  • Integer loop variables in for/repeat loops use blocking — excluded.
  • Parameter / localparams are not reg assignments — excluded.
  • $display / $monitor arguments are not LHS assignments — excluded.
"""

from __future__ import annotations

import re
from typing import List

from ..models import CheckID, Finding, Severity
from ..parser import ParsedFile, AlwaysKind

_RE_BLOCKING_ASSIGN = re.compile(
    r"(?<!\s)"          # not preceded by nothing (avoid matching <=)
    r"(?<![<>!])"       # not <= >= !=
    r"\s*=\s*"          # the assignment =
    r"(?!=)"            # not ==
)
_RE_LOOP_VAR = re.compile(r"\bfor\s*\(.*?=", re.S)
_RE_SYS_TASK = re.compile(r"\$\w+\s*\(")


def check_blocking_in_ff(pf: ParsedFile) -> List[Finding]:
    findings: List[Finding] = []

    for ab in pf.always_blocks:
        if ab.kind not in (AlwaysKind.FF, AlwaysKind.GENERIC):
            continue
        if not (ab.has_posedge or ab.has_negedge):
            continue  # not a clocked block

        lines = pf.lines[ab.start_line - 1 : ab.end_line]
        for li in lines:
            s = li.stripped
            if not s:
                continue
            # Skip loop variable initialisers
            if _RE_LOOP_VAR.search(s):
                continue
            # Skip system task calls
            if _RE_SYS_TASK.search(s):
                continue
            # Skip wire/reg/logic declarations
            if re.match(r"\b(?:wire|reg|logic|integer|int|bit|byte|real)\b", s):
                continue
            # Remove non-blocking <= so it doesn't confuse the regex
            clean = re.sub(r"<=", "  ", s)
            # Remove ==, >=, !=
            clean = re.sub(r"[<>!]=", "  ", clean)
            if re.search(r"(?<![<>!])\w[\w\[\]:. ]*\s*=\s*(?!=)", clean):
                findings.append(Finding(
                    check_id=CheckID.RTL_E004,
                    severity=Severity.ERROR,
                    message=(
                        "Blocking assignment '=' inside clocked always block. "
                        "Use non-blocking '<=' for sequential logic to avoid "
                        "race conditions and simulation/synthesis mismatch."
                    ),
                    location=pf.location(li.number),
                    fix_hint="Replace '=' with '<=' for all register assignments in this block.",
                ))

    return findings
