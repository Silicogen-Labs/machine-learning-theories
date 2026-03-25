"""
RTL_W007 — CDC: signal crosses clock domains without synchroniser.

Algorithm (structural, conservative):
  1. Identify all distinct clocks in the module (from posedge/negedge always blocks).
     Single-clock files → skip entirely.
  2. For each always block, record which signals it assigns and which clock drives it.
     → signal_writers: Dict[signal_name, clock_name]
  3. For each always block clocked by CLK_B, examine RHS of all assignments.
     If RHS signal is in signal_writers with a different clock CLK_A, and
     that signal does NOT appear as the LHS of another CLK_B block that is a
     plausible sync stage (single assignment, same-width, no logic), flag W007.

Conservative rule: only flag DIRECT reads. If a signal passes through ANY
CLK_B register first (sync_ff1 → sync_ff2 pattern) we treat it as synchronised
even if the chain is only one stage long. This avoids false positives on designs
that use single-FF syncs (which are technically metastable but in design intent).

Sync-stage identification: a block is treated as a sync stage (not flagged) only
if at least one of its LHS signals is subsequently consumed (read as RHS) by
another block in the same clock domain. This distinguishes true synchroniser
registers (whose outputs feed downstream logic) from direct-consuming registers
(whose outputs are endpoints such as module outputs).

References:
  Synopsys SpyGlass CDC: CDC_GLITCH.
  Mentor Questa CDC: cdc_data rule.
  IEEE 1800.2 (UVM) CDC analysis guidelines.
"""

from __future__ import annotations

import re
from typing import Dict, List, Set

from ..models import CheckID, Finding, Severity
from ..parser import AlwaysKind, ParsedFile

_RE_RHS_SIGNAL = re.compile(r"(?:<=|=)\s*(\w+)\s*;")
# Note: _RE_LHS_SIGNAL matches only non-blocking (<= ) assignments intentionally.
# Blocking (=) assignments inside FF blocks are unusual (RTL_E004 territory) and
# are intentionally excluded from signal_writer to stay conservative — a miss is
# better than a false positive on temporaries.
_RE_LHS_SIGNAL = re.compile(r"(\w+)\s*(?:\[.*?\])?\s*<=")

_KEYWORDS = frozenset(("if", "else", "begin", "end", "always", "case",
                        "casex", "casez", "for", "while", "repeat"))


def _get_block_clock(ab) -> str:
    """Return the posedge/negedge clock name for this always block, or ''."""
    m = re.search(r"\b(?:posedge|negedge)\s+(\w+)", ab.sensitivity, re.I)
    return m.group(1).lower() if m else ""


def _block_signals(pf: ParsedFile, ab) -> tuple[list[str], list[str]]:
    """Return (distinct_lhs_signals, distinct_rhs_signals) for an always block."""
    lhs: list[str] = []
    rhs: list[str] = []
    seen_lhs: set[str] = set()
    seen_rhs: set[str] = set()
    lines = pf.lines[ab.start_line - 1 : ab.end_line]
    for li in lines:
        for m in _RE_LHS_SIGNAL.finditer(li.stripped):
            s = m.group(1)
            if s not in _KEYWORDS and s not in seen_lhs:
                lhs.append(s)
                seen_lhs.add(s)
        for m in _RE_RHS_SIGNAL.finditer(li.stripped):
            s = m.group(1)
            if s not in _KEYWORDS and s not in seen_rhs:
                rhs.append(s)
                seen_rhs.add(s)
    return lhs, rhs


def check_cdc(pf: ParsedFile) -> List[Finding]:
    findings: List[Finding] = []

    # Only sequential (FF) blocks participate in CDC analysis
    ff_blocks = [ab for ab in pf.always_blocks
                 if ab.kind == AlwaysKind.FF
                 or (ab.kind == AlwaysKind.GENERIC and ab.has_posedge)]

    if len(ff_blocks) < 2:
        return findings  # single-clock or no FF blocks → skip

    # ── Step 1: collect distinct clocks ───────────────────────────────────
    clocks: Set[str] = set()
    for ab in ff_blocks:
        clk = _get_block_clock(ab)
        if clk:
            clocks.add(clk)

    if len(clocks) < 2:
        return findings  # genuinely single-clock design

    # ── Step 2: build signal → clock writer map ───────────────────────────
    signal_writer: Dict[str, str] = {}  # signal_name → clock_name

    for ab in ff_blocks:
        clk = _get_block_clock(ab)
        if not clk:
            continue
        lhs, _ = _block_signals(pf, ab)
        for sig in lhs:
            signal_writer[sig] = clk

    # ── Step 3: identify sync-stage blocks ────────────────────────────────
    # A block qualifies as a sync stage if:
    #   (a) it reads at least one signal from a foreign clock domain, AND
    #   (b) at least one of its LHS signals is read as RHS by another block
    #       in the SAME clock domain (i.e., its output feeds downstream logic
    #       rather than being a terminal consumer).
    # When a block is identified as a sync stage, we absorb its foreign RHS
    # signals AND all of its LHS signals into sync_absorbed so that downstream
    # blocks that read those sync outputs are not flagged.

    # Pre-compute (lhs, rhs) per block for reuse
    block_io: Dict[int, tuple[list[str], list[str]]] = {}
    for ab in ff_blocks:
        block_io[ab.start_line] = _block_signals(pf, ab)

    # Build: clock → set of all RHS signals read across all blocks of that clock
    clock_rhs: Dict[str, Set[str]] = {}
    for ab in ff_blocks:
        clk = _get_block_clock(ab)
        if not clk:
            continue
        _, rhs = block_io[ab.start_line]
        clock_rhs.setdefault(clk, set()).update(rhs)

    sync_absorbed: Set[str] = set()

    for ab in ff_blocks:
        clk = _get_block_clock(ab)
        if not clk:
            continue
        lhs, rhs = block_io[ab.start_line]

        # Check (a): does this block read a foreign-clock signal?
        foreign_rhs = [s for s in rhs if signal_writer.get(s, clk) != clk]
        if not foreign_rhs:
            continue

        # Check (b): is at least one LHS output consumed by another same-clock block?
        # We approximate "another block" by checking if any LHS signal appears in the
        # global set of RHS signals for this clock domain, excluding what this block
        # itself reads (use full clock_rhs set — if LHS ∈ clock_rhs[clk], some block
        # in this domain reads it; the block could be this one reading its own output,
        # but that's rare and conservative misses are acceptable).
        same_clk_rhs = clock_rhs.get(clk, set())
        lhs_consumed_downstream = any(s in same_clk_rhs for s in lhs)

        if lhs_consumed_downstream:
            # This is a plausible sync stage — absorb foreign inputs and outputs
            for s in foreign_rhs:
                sync_absorbed.add(s)
            for s in lhs:
                sync_absorbed.add(s)

    # ── Step 4: flag direct cross-domain reads ─────────────────────────────
    for ab in ff_blocks:
        clk = _get_block_clock(ab)
        if not clk:
            continue
        lines = pf.lines[ab.start_line - 1 : ab.end_line]
        for li in lines:
            for m in _RE_RHS_SIGNAL.finditer(li.stripped):
                sig = m.group(1)
                if sig in _KEYWORDS or not (sig[0].isalpha() or sig[0] == "_"):
                    continue  # skip keywords and numeric literals (e.g. 1'b0)
                writer_clk = signal_writer.get(sig, "")
                if writer_clk and writer_clk != clk and sig not in sync_absorbed:
                    findings.append(Finding(
                        check_id=CheckID.RTL_W007,
                        severity=Severity.WARNING,
                        message=(
                            f"CDC hazard: signal '{sig}' (written in '{writer_clk}' "
                            f"domain) read directly in '{clk}' domain at line "
                            f"{li.number} with no synchroniser. Metastability risk."
                        ),
                        location=pf.location(li.number),
                        fix_hint=(
                            f"Insert a 2-FF synchroniser: declare sync_ff1, sync_ff2 "
                            f"in the '{clk}' domain clocked block and chain "
                            f"sync_ff1 <= {sig}; sync_ff2 <= sync_ff1; "
                            f"then use sync_ff2 instead of '{sig}'."
                        ),
                    ))
                    break  # report at most one W007 per always block to avoid noise

    return findings
