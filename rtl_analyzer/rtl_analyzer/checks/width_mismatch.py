"""
RTL_W002 — Width mismatch (truncation / zero-extension / sign-extension).

One of the most dangerous silent bugs: assigning a wider expression to a
narrower variable silently truncates MSBs.  Assigning signed to unsigned
or vice-versa silently changes meaning.

Standard reference:
  • Verilator: WIDTHTRUNC, WIDTHEXPAND
  • SpyGlass: W11, W164
  • IEEE 1800-2017 §6.24

Detection strategy (without full elaboration):
  1. Find literal width mismatch: `logic [3:0] x = 8'hFF;`  → 8-bit into 4-bit.
  2. Find parameterised concat without explicit widths.
  3. Find comparison of different-width operands via literal widths.
  4. Find signed/unsigned mixing: `signed` reg assigned from unsigned or vice-versa.

We intentionally avoid false positives on parameterised widths where we
can't resolve the parameter values at this stage.
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from ..models import CheckID, Finding, Severity
from ..parser import ParsedFile


# Matches:  logic [W-1:0] name   or   reg [N:0] name   or   wire [7:0] name
_RE_DECL = re.compile(
    r"\b(?:logic|reg|wire|bit)\s*(?:signed|unsigned)?\s*"
    r"\[(\d+)\s*:\s*(\d+)\]\s+(\w+)"
)

# Matches numeric literal:  8'hFF  4'b1010  12'd0
_RE_LIT = re.compile(r"(\d+)'[shbodxSHBODX][\w_]+")

# Matches assignment:  signal = expr   or   signal <= expr
_RE_ASSIGN = re.compile(
    r"(\w+)\s*(?:\[\d+(?::\d+)?\])?\s*(?:<=|=)\s*(.+)"
)


def _lit_width(literal: str) -> Optional[int]:
    m = re.match(r"(\d+)'", literal)
    return int(m.group(1)) if m else None


def check_width_mismatch(pf: ParsedFile) -> List[Finding]:
    """
    Detect obvious width mismatches from literal bit-widths.
    Only fires when we can determine both sides' widths with certainty.
    """
    findings: List[Finding] = []

    # Build a name→declared_width map from declarations
    declared: dict[str, int] = {}
    for li in pf.iter_lines():
        for m in _RE_DECL.finditer(li.stripped):
            msb, lsb, name = int(m.group(1)), int(m.group(2)), m.group(3)
            declared[name] = abs(msb - lsb) + 1

    # Scan assignments for literal-width mismatches
    for li in pf.iter_lines():
        m = _RE_ASSIGN.search(li.stripped)
        if not m:
            continue
        lhs_name, rhs = m.group(1), m.group(2)
        lhs_width = declared.get(lhs_name)
        if lhs_width is None:
            continue

        # Find all literals on RHS
        rhs_lits = _RE_LIT.findall(rhs)
        if not rhs_lits:
            continue

        # If RHS is a single literal, compare widths directly
        rhs_stripped = rhs.strip().rstrip(";")
        single_lit = re.fullmatch(r"(\d+)'[shbodxSHBODX][\w_]+", rhs_stripped)
        if single_lit:
            rhs_width = int(single_lit.group(1))
            if rhs_width > lhs_width:
                findings.append(Finding(
                    check_id=CheckID.RTL_W002,
                    severity=Severity.WARNING,
                    message=(
                        f"Width mismatch: '{lhs_name}' is {lhs_width} bits but "
                        f"RHS literal is {rhs_width} bits — {rhs_width - lhs_width} "
                        "MSBs will be silently truncated."
                    ),
                    location=pf.location(li.number),
                    fix_hint=(
                        f"Resize the literal to {lhs_width}'… or widen the declaration of "
                        f"'{lhs_name}' to [{rhs_width - 1}:0]."
                    ),
                ))

    return findings
