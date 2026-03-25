"""
RTL_E001 — Unintended latch inference.

The #1 RTL bug across every industry source.  Occurs when a combinational
block does not assign a signal on all possible branches of an if/case
statement.  The synthesiser infers a latch to "remember" the previous value,
which:
  • Creates a level-sensitive memory element not in the design intent.
  • Causes timing analysis failures (no clock pin → no setup/hold checks).
  • Creates simulation/synthesis mismatches (sim starts at X, hw keeps old value).

Standard reference:
  • Verilator: LATCH
  • Verible: no direct equivalent (rule-based style only)
  • SpyGlass: W415 (incomplete assignment)

Algorithm:
  1. Find all combinational always blocks (always_comb, always @(*)).
  2. For each signal assigned anywhere in the block, check whether
     it is assigned in *every* branch of every if/case.
  3. If a signal is missing from any else/default branch → latch warning.

Conservative approach: only flag when we can clearly see a missing else
or missing default — we do not attempt full branch coverage of complex
nested if-else trees (that would need a proper dataflow analyser).
"""

from __future__ import annotations

import re
from typing import List, Set

from ..models import CheckID, Finding, Severity
from ..parser import ParsedFile, AlwaysKind


_RE_IF_NO_ELSE = re.compile(r"\bif\b.*\bbegin\b|\bif\b.*\n")
_RE_CASE = re.compile(r"\bcase[xz]?\s*\(")
_RE_DEFAULT = re.compile(r"\bdefault\b\s*:")


def _has_else(block_text: str) -> bool:
    return bool(re.search(r"\belse\b", block_text))


def _has_default(block_text: str) -> bool:
    return bool(_RE_DEFAULT.search(block_text))


def _signals_in_lhs(block_lines_text: List[str]) -> Set[str]:
    sigs: Set[str] = set()
    for line in block_lines_text:
        # Match LHS of both blocking and non-blocking
        for m in re.finditer(r"(\w+)\s*(?:\[.*?\])?\s*[<]?=\s*(?!=)", line):
            name = m.group(1)
            if name not in (
                "if", "else", "case", "casez", "casex",
                "begin", "end", "for", "while", "repeat", "assign",
                "default",
            ):
                sigs.add(name)
    return sigs


def _signals_with_default_before_if(block_lines_text: List[str]) -> set:
    """
    Return signals that have an unconditional assignment before the first
    'if' keyword in the block — these are pre-defaulted and cannot infer
    a latch regardless of whether the if has an else.
    """
    pre: set = set()
    for line in block_lines_text:
        if re.search(r"\bif\b", line):
            break  # stop at first conditional
        for m in re.finditer(r"(\w+)\s*(?:\[.*?\])?\s*[<]?=\s*(?!=)", line):
            pre.add(m.group(1))
    return pre


def check_latch_inference(pf: ParsedFile) -> List[Finding]:
    findings: List[Finding] = []

    for ab in pf.always_blocks:
        if ab.kind != AlwaysKind.COMB:
            continue

        lines = pf.lines[ab.start_line - 1 : ab.end_line]
        texts = [li.stripped for li in lines]
        block_text = "\n".join(texts)

        # ── Check 1: if without else ────────────────────────────────────────
        has_if = bool(re.search(r"\bif\b", block_text))
        if has_if and not _has_else(block_text):
            lhs_sigs = _signals_in_lhs(texts)
            # Remove signals that have a default assignment before the first if
            pre_defaulted = _signals_with_default_before_if(texts)
            lhs_sigs -= pre_defaulted
            if lhs_sigs:
                for li in lines:
                    if re.search(r"\bif\b", li.stripped):
                        findings.append(Finding(
                            check_id=CheckID.RTL_E001,
                            severity=Severity.ERROR,
                            message=(
                                f"Latch inference: combinational block has 'if' without 'else'. "
                                f"Signals {sorted(lhs_sigs)} not assigned on all paths. "
                                "Synthesis will infer a latch."
                            ),
                            location=pf.location(li.number),
                            fix_hint=(
                                "Add an 'else' branch assigning a default value, or add "
                                "a default assignment at the top of the always block "
                                "(e.g. signal = '0;)."
                            ),
                        ))
                        break  # one finding per block

        # ── Check 2: case without default ──────────────────────────────────
        if _RE_CASE.search(block_text) and not _has_default(block_text):
            lhs_sigs = _signals_in_lhs(texts)
            pre_defaulted = _signals_with_default_before_if(texts)
            lhs_sigs -= pre_defaulted
            if lhs_sigs:
                for li in lines:
                    if _RE_CASE.search(li.stripped):
                        findings.append(Finding(
                            check_id=CheckID.RTL_E001,
                            severity=Severity.ERROR,
                            message=(
                                f"Latch inference: case statement has no 'default' branch. "
                                f"Signals {sorted(lhs_sigs)} unassigned for unlisted states. "
                                "Synthesis will infer a latch."
                            ),
                            location=pf.location(li.number),
                            fix_hint=(
                                "Add 'default: signal = <default_value>;' to the case statement, "
                                "or use unique case / priority case with full coverage."
                            ),
                        ))
                        break

    return findings
