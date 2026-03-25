"""
RTL_W004 — Missing reset on state register (flip-flop).

Flip-flops that are not reset start in an undefined state (X in simulation,
random value in hardware).  For FSM state registers this is catastrophic —
the machine starts in an undefined state.  For data registers it can cause
subtle data-path corruption until the first valid write.

Standard reference:
  • Verilator: no direct check (simulation starts X)
  • SpyGlass: W17 (no reset)

Algorithm:
  1. Find clocked always blocks (posedge/negedge).
  2. Identify signals assigned in the block that look like state registers
     (assigned from a case-FSM or named *state*, *st*, *fsm*).
  3. If the block has no reset signal (rst, reset, arst, …) → warning.

Conservative: only fires on blocks containing case statements or signals
with state-like names.  Does not fire on every FF (too noisy).
"""

from __future__ import annotations

import re
from typing import List

from ..models import CheckID, Finding, Severity
from ..parser import ParsedFile, AlwaysKind


_RE_STATE_NAME = re.compile(r"\b(\w*(?:state|st|fsm|cur|next|current|nxt)\w*)\b", re.I)
_RE_CASE = re.compile(r"\bcase[xz]?\b")


def check_missing_reset(pf: ParsedFile) -> List[Finding]:
    findings: List[Finding] = []

    for ab in pf.always_blocks:
        if ab.kind not in (AlwaysKind.FF, AlwaysKind.GENERIC):
            continue
        if not (ab.has_posedge or ab.has_negedge):
            continue
        if ab.has_reset:
            continue  # reset signal present — OK

        lines = pf.lines[ab.start_line - 1 : ab.end_line]
        block_text = "\n".join(li.stripped for li in lines)

        # Only flag if: has a case statement (FSM) or state-like signal names
        has_case = bool(_RE_CASE.search(block_text))
        has_state_sig = bool(_RE_STATE_NAME.search(block_text))

        if has_case or has_state_sig:
            findings.append(Finding(
                check_id=CheckID.RTL_W004,
                severity=Severity.WARNING,
                message=(
                    "Clocked always block with FSM/state register has no reset signal. "
                    "The register will start in an unknown state; "
                    "FSMs can lock up on power-on or glitch recovery."
                ),
                location=pf.location(ab.start_line),
                fix_hint=(
                    "Add a synchronous reset: if (rst) state <= RESET_STATE; "
                    "or an asynchronous reset: always_ff @(posedge clk or posedge rst)."
                ),
            ))

    return findings
