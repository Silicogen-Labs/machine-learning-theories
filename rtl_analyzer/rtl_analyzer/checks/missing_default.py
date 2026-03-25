"""
RTL_W001 — Missing default in case statement.

Separate from the latch check: this fires even in sequential blocks where
a missing default doesn't infer a latch but does leave the FSM in an
undefined state if an illegal/unreachable state value is ever reached
(can happen due to SEU, reset glitches, or CDC metastability).

Standard reference:
  • Verilator: CASEINCOMPLETE
  • Verible: case-missing-default
  • SpyGlass: W13 (missing default clause)
"""

from __future__ import annotations

import re
from typing import List

from ..models import CheckID, Finding, Severity
from ..parser import ParsedFile, AlwaysKind


_RE_CASE_OPEN = re.compile(r"\bcase[xz]?\s*\(([^)]*)\)")
_RE_DEFAULT = re.compile(r"\bdefault\b\s*:")


def check_missing_default(pf: ParsedFile) -> List[Finding]:
    findings: List[Finding] = []

    for ab in pf.always_blocks:
        lines = pf.lines[ab.start_line - 1 : ab.end_line]

        i = 0
        while i < len(lines):
            li = lines[i]
            m = _RE_CASE_OPEN.search(li.stripped)
            if not m:
                i += 1
                continue

            # Collect the case block until matching endcase
            case_text_parts = []
            depth = 1
            j = i
            while j < len(lines) and depth > 0:
                s = lines[j].stripped
                opens  = len(re.findall(r"\bcase[xz]?\b", s))
                closes = len(re.findall(r"\bendcase\b", s))
                # The opening line itself was already counted as depth=1 before the loop
                # so only add net opens/closes from subsequent lines
                if j == i:
                    depth += opens - 1 - closes   # -1: the opener we started with
                else:
                    depth += opens - closes
                case_text_parts.append(s)
                j += 1

            case_block = "\n".join(case_text_parts)
            if not _RE_DEFAULT.search(case_block):
                # Only report if not already caught by latch_inference
                # (sequential blocks deserve their own warning)
                findings.append(Finding(
                    check_id=CheckID.RTL_W001,
                    severity=Severity.WARNING,
                    message=(
                        f"Case statement on '{m.group(1).strip()}' has no 'default' branch. "
                        "Illegal/unreachable states leave outputs undefined, "
                        "risking lockup after SEU or reset glitch."
                    ),
                    location=pf.location(li.number),
                    fix_hint=(
                        "Add 'default: <assignments>;' to handle unlisted states. "
                        "For FSMs, consider 'default: state <= IDLE;' to force recovery."
                    ),
                ))
            i = j

    return findings
