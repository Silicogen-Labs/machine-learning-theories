"""
RTL_E006 — FSM unreachable state.
RTL_W006 — FSM next-state logic missing default branch.

Algorithm (regex-based, conservative):
  1. Find typedef enum { STATE_A, STATE_B, ... } in comment-stripped source.
  2. Find the always_comb block that has case(<state_reg>).
  3. Collect all state names that appear as:
     a. RHS of next = <STATE> or next_state = <STATE> assignments in the comb block.
     b. RHS of <= <STATE> anywhere in the file (captures FF reset assignments).
     c. Case labels in the comb block (a decode target is reachable by definition).
  4. States in enum but NOT in any of the above → RTL_E006.
  5. If no 'default:' in that case block → RTL_W006.

References:
  SpyGlass FSM_5 (unreachable state), FSM_1 (incomplete state transitions).
  Synopsys VC SpyGlass CDC: FSM checks.
"""

from __future__ import annotations

import re
from typing import List, Set

from ..models import CheckID, Finding, Severity
from ..parser import ParsedFile, AlwaysKind

_RE_TYPEDEF_ENUM = re.compile(
    r"\btypedef\s+enum\b.*?\{([^}]+)\}", re.DOTALL
)
_RE_STATE_ASSIGN = re.compile(r"\bnext\s*(?:_state)?\s*=\s*(\w+)\s*;")
_RE_CASE_OPEN = re.compile(r"\bcase\s*\(\s*(\w+)\s*\)")
_RE_DEFAULT = re.compile(r"\bdefault\s*:")


def _extract_enum_states(source: str) -> Set[str]:
    """Return all identifiers listed inside typedef enum { ... }."""
    states: Set[str] = set()
    for m in _RE_TYPEDEF_ENUM.finditer(source):
        body = m.group(1)
        for item in re.split(r"[,\s]+", body):
            item = re.sub(r"=.*", "", item).strip()
            if re.match(r"^[A-Za-z_]\w*$", item):
                states.add(item)
    return states


def check_fsm(pf: ParsedFile) -> List[Finding]:
    findings: List[Finding] = []

    # Use comment-stripped source to avoid matching commented-out enums
    stripped_source = "\n".join(li.stripped for li in pf.lines)
    enum_states = _extract_enum_states(stripped_source)
    if not enum_states:
        return findings   # no enum FSM in this file

    for ab in pf.always_blocks:
        if ab.kind not in (AlwaysKind.COMB, AlwaysKind.GENERIC):
            continue

        lines = pf.lines[ab.start_line - 1 : ab.end_line]
        block_text = "\n".join(li.stripped for li in lines)

        # Only process blocks that contain a case() statement
        case_m = _RE_CASE_OPEN.search(block_text)
        if not case_m:
            continue

        # ── RTL_W006: no default branch ───────────────────────────────────
        # Conservative note: W006 fires on any comb case() block in a file
        # that contains a typedef enum. In practice, FSM files rarely mix
        # unrelated case() blocks at the same always_comb level; the risk
        # of false positives on non-FSM case blocks is low but documented.
        if not _RE_DEFAULT.search(block_text):
            findings.append(Finding(
                check_id=CheckID.RTL_W006,
                severity=Severity.WARNING,
                message=(
                    f"FSM next-state logic: case({case_m.group(1)}) has no 'default' "
                    "branch. Unencoded states will resolve to X in simulation, "
                    "unpredictable in hardware."
                ),
                location=pf.location(ab.start_line),
                fix_hint=(
                    "Add 'default: next_state = <reset_state>;' to the case block."
                ),
            ))

        # ── RTL_E006: unreachable states ──────────────────────────────────
        assigned_states: Set[str] = set()
        for m in _RE_STATE_ASSIGN.finditer(block_text):
            name = m.group(1)
            if name in enum_states:
                assigned_states.add(name)

        # The reset/entry state may appear in the FF block, not comb
        # so scan the whole file for `<reg> <= STATE` patterns too
        for m in re.finditer(r"<=\s*(\w+)\s*;", stripped_source):
            name = m.group(1)
            if name in enum_states:
                assigned_states.add(name)

        unreachable = enum_states - assigned_states
        # Remove states that appear as case labels (they are reachable by
        # definition even if not in a next= assignment — e.g. DONE: done=1)
        for li in lines:
            for m in re.finditer(r"^\s*(\w+)\s*:", li.stripped):
                name = m.group(1)
                if name in enum_states:
                    unreachable.discard(name)

        if unreachable:
            findings.append(Finding(
                check_id=CheckID.RTL_E006,
                severity=Severity.ERROR,
                message=(
                    f"FSM has unreachable state(s): {sorted(unreachable)}. "
                    "No transition leads to these states; they are dead code."
                ),
                location=pf.location(ab.start_line),
                fix_hint=(
                    "Either add a transition into the unreachable state(s), or "
                    "remove them from the enum and any case labels."
                ),
            ))

    return findings
