"""
RTL_W005 — Simulation/synthesis mismatch risk.

Constructs that behave differently between simulation and synthesis:
  1. `initial` blocks  — ignored by synthesis, executed in simulation.
  2. `#delay` statements — ignored by synthesis, advance simulation time.
  3. `fork/join` — not synthesisable.
  4. Non-constant loop bounds — synthesis may unroll differently.
  5. `$display/$monitor/$finish` in synthesisable code — ignored by synthesis.

Standard reference:
  • Verilator: INITIALDLY
  • SpyGlass: W95 (delay in synthesisable code), W29 (initial block)
"""

from __future__ import annotations

import re
from typing import List

from ..models import CheckID, Finding, Severity
from ..parser import ParsedFile


_CHECKS = [
    (
        re.compile(r"^\s*initial\b"),
        "RTL_W005a",
        "'initial' block is ignored by synthesis. "
        "Use always_ff with reset to initialise registers instead.",
        "Replace 'initial' with reset logic inside always_ff.",
    ),
    (
        re.compile(r"#\s*\d+"),
        "RTL_W005b",
        "Delay '#N' is ignored by synthesis but advances simulation time, "
        "causing simulation/synthesis mismatch.",
        "Remove timing delays from synthesisable RTL; use clock edges for timing.",
    ),
    (
        re.compile(r"\bfork\b"),
        "RTL_W005c",
        "'fork/join' is not synthesisable. Parallel threads are undefined in hardware.",
        "Refactor parallel behaviour into separate always blocks or state machines.",
    ),
]


def check_sim_synth_mismatch(pf: ParsedFile) -> List[Finding]:
    findings: List[Finding] = []

    for li in pf.iter_lines():
        s = li.stripped
        for pattern, tag, msg, hint in _CHECKS:
            if pattern.search(s):
                findings.append(Finding(
                    check_id=CheckID.RTL_W005,
                    severity=Severity.WARNING,
                    message=f"[{tag}] {msg}",
                    location=pf.location(li.number),
                    fix_hint=hint,
                ))
                break  # one finding per line max

    return findings
