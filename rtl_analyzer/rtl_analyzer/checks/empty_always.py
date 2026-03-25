"""
RTL_I003 — Empty always block.

An always block with no statements inside is almost certainly dead code: a
stub that was never filled in, or a block whose body was deleted but the
skeleton left behind.  Synthesis tools silently ignore it; simulation tools
may also ignore it; but it clutters the design and can mask real intent.

Standard reference:
  • Verilator: BLKLOOPINIT (adjacent, not identical) — no direct equivalent
  • Verible: no equivalent
  • SpyGlass: W16 (empty block)
  • IEEE 1800-2012 §9.2: "The statement in a procedural block may be empty."

Algorithm:
  1. For each always block extracted by the parser, collect the lines between
     `begin` and `end`.
  2. If those lines contain no statements (only whitespace / comments after
     stripping), the block is empty → RTL_I003.

Conservative rule:
  A block with only a comment (e.g. // TODO) is still flagged as empty —
  the comment does not constitute a statement.  This matches SpyGlass W16
  behaviour.
"""

from __future__ import annotations

import re
from typing import List

from ..models import CheckID, Finding, Severity
from ..parser import ParsedFile

# Tokens that count as real statements inside an always block.
_RE_STATEMENT = re.compile(
    r"""
    (?:
        \w+\s*(?:\[.*?\])?\s*<=?\s*   # assignment LHS
      | \bif\b                         # conditional
      | \bcase[xz]?\b                  # case statement
      | \bfor\b                        # loop
      | \bwhile\b                      # loop
      | \bdisplay\b                    # system task
      | \$\w+                          # any system task/function call
    )
    """,
    re.VERBOSE,
)


def check_empty_always(pf: ParsedFile) -> List[Finding]:
    """
    RTL_I003: flag always blocks that contain no statements.

    References:
      SpyGlass W16 — empty block.
    """
    findings: List[Finding] = []

    for ab in pf.always_blocks:
        lines = pf.lines[ab.start_line - 1 : ab.end_line]
        # Collect stripped text of lines that are *inside* the block body
        # (i.e., not the `always @(...)` header line itself).
        body_stripped = [li.stripped for li in lines[1:]]

        # Remove structural keywords that are not statements.
        # After removing begin/end/always keywords, if nothing is left
        # that matches a real statement pattern → empty block.
        non_structural = []
        for s in body_stripped:
            # Remove the enclosing begin/end tokens
            s2 = re.sub(r"\bbegin\b|\bend\b", "", s).strip()
            if s2:
                non_structural.append(s2)

        has_statements = any(
            _RE_STATEMENT.search(s) for s in non_structural
        )

        if not has_statements:
            findings.append(Finding(
                check_id=CheckID.RTL_I003,
                severity=Severity.INFO,
                message=(
                    "Empty always block: no statements found between begin/end. "
                    "This is dead code and will be ignored by synthesis."
                ),
                location=pf.location(ab.start_line),
                fix_hint=(
                    "Either add the intended logic or remove the always block entirely."
                ),
            ))

    return findings
