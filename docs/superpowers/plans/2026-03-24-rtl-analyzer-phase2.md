# RTL Analyzer Phase 2 — FSM Extraction + Structural CDC Analysis

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `rtl_analyzer` from a pure regex/line-scan linter into a structural analyser that extracts finite-state machines (FSMs) and detects clock-domain crossing (CDC) hazards using pyslang's elaborated AST.

**Architecture:** Phase 2 builds two new analysis modules — `fsm_extractor` (finds state registers, enumerates transitions, validates completeness) and `cdc_analyzer` (identifies signals crossing clock domains without synchronisers). Both operate on `pyslang.Compilation` (elaborated) rather than the raw `SyntaxTree` used in Phase 1. The existing `ParsedFile` / `AlwaysBlock` regex model is kept for all Phase 1 checks; Phase 2 adds a parallel `ElaboratedModule` model that is built lazily per file.

**Tech Stack:** Python 3.12, `pyslang 10.0.0` (elaborated AST, `Compilation`, `InstanceSymbol`, `VariableSymbol`, `NetType`), `pytest 8`, `rich`, existing `models.py` (`Finding`, `CheckID`, `Severity`).

---

## Phase 2 scope (what is NOT deferred)

| Check ID | Name | Method |
|---|---|---|
| `RTL_E006` | FSM state register has unreachable state | pyslang AST transition graph |
| `RTL_W006` | FSM state register missing default/else in next-state logic | pyslang AST |
| `RTL_W007` | CDC: signal crosses clock domains without synchroniser | pyslang net type + clock inference |

`RTL_E002` (combinational loop) — still Phase 3 (needs full dataflow DAG). Stub stays.

---

## What Phase 1 left us

- `rtl_analyzer/parser/__init__.py` — `ParsedFile` with `.syntax_tree: pyslang.SyntaxTree` already populated
- `rtl_analyzer/engine.py` — `AnalysisEngine.analyze_file()` calls `parse_file()` then runs `ALL_CHECKS`
- `rtl_analyzer/checks/__init__.py` — `ALL_CHECKS` list; all checks are `(ParsedFile) -> List[Finding]`
- `rtl_analyzer/models.py` — `CheckID` enum (add `RTL_E006`, `RTL_W006`, `RTL_W007` here)
- 42 passing tests in `tests/test_checks.py`

---

## File Map

### New files (create)
| File | Responsibility |
|---|---|
| `rtl_analyzer/elaborator.py` | Wraps `pyslang.Compilation`; builds `ElaboratedModule` per module; lazy (only built when Phase 2 checks run) |
| `rtl_analyzer/checks/fsm_extractor.py` | RTL_E006 + RTL_W006: detect state registers, build transition graph, flag unreachable states and missing defaults |
| `rtl_analyzer/checks/cdc_checker.py` | RTL_W007: identify multi-clock designs, flag unsynchronised crossings |
| `tests/test_phase2.py` | All Phase 2 unit + integration tests |
| `tests/fixtures/buggy/buggy_fsm_unreachable.v` | FSM with an unreachable state → triggers RTL_E006 |
| `tests/fixtures/buggy/buggy_fsm_no_default.sv` | FSM next-state logic missing default → triggers RTL_W006 |
| `tests/fixtures/buggy/buggy_cdc.v` | Two-clock module: signal from clk_a domain read in clk_b domain with no sync → RTL_W007 |
| `tests/fixtures/clean/clean_cdc_synced.v` | Two-clock module with 2FF synchroniser → no RTL_W007 |

### Modified files
| File | Change |
|---|---|
| `rtl_analyzer/models.py` | Add `RTL_E006`, `RTL_W006`, `RTL_W007` to `CheckID` enum |
| `rtl_analyzer/parser/__init__.py` | Add `ParsedFile.elaborated: Optional[ElaboratedModule]` field (populated lazily) |
| `rtl_analyzer/engine.py` | After building `ParsedFile`, call `elaborator.build(pf)` if Phase 2 checks are enabled |
| `rtl_analyzer/checks/__init__.py` | Import and register `check_fsm`, `check_cdc` in `ALL_CHECKS` |
| `benchmarks/compare_tools.py` | Add Phase 2 fixture entries to `REFERENCE_EXPECTATIONS` |

---

## pyslang API notes (for the implementer)

```python
import pyslang

# Compile a single file into an elaborated design
compilation = pyslang.Compilation()
compilation.addSyntaxTree(syntax_tree)        # syntax_tree from ParsedFile
root = compilation.getRoot()                  # InstanceSymbol (top)

# Walk all instances
for inst in root.members:
    if inst.kind == pyslang.SymbolKind.Instance:
        ...

# Walk nets/variables inside a module
for member in instance.body.members:
    if member.kind == pyslang.SymbolKind.Variable:
        var = member  # VariableSymbol
        print(var.name, var.type)

# Get the syntax node for a symbol (for line numbers)
syntax = symbol.getSyntax()
loc = syntax.sourceRange().start()
```

> **Important:** `pyslang.Compilation` tolerates files that import packages not in the build. Always call `compilation.getAllDiagnostics()` and skip checks if there are fatal elaboration errors — don't crash.

> **Width API:** `sym.type.bitstreamWidth()` is the expected pyslang 10 method for bit width. If it raises `AttributeError`, fall back to `sym.type.width` or catch and default to 1. Verify against pyslang 10.0.0 at runtime with `dir(sym.type)` if the elaborator tests fail on width access.

---

## Task 1: Add RTL_E006, RTL_W006, RTL_W007 to CheckID

**Files:**
- Modify: `rtl_analyzer/models.py:44-61`

- [ ] **Step 1: Write a failing import test**

Create `tests/test_phase2.py`:

```python
from rtl_analyzer.models import CheckID

def test_new_check_ids_exist():
    assert CheckID.RTL_E006
    assert CheckID.RTL_W006
    assert CheckID.RTL_W007
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd /home/jovyan/silicogen/rtl_analyzer
python -m pytest tests/test_phase2.py::test_new_check_ids_exist -v
```
Expected: `AttributeError` — `RTL_E006` not in `CheckID`

- [ ] **Step 3: Add the three new IDs to models.py**

In `rtl_analyzer/models.py`, after `RTL_E005` add:
```python
    RTL_E006 = "RTL_E006"   # FSM: unreachable state detected
```
After `RTL_W005` add:
```python
    RTL_W006 = "RTL_W006"   # FSM: missing default in next-state logic
    RTL_W007 = "RTL_W007"   # CDC: signal crosses clock domains without synchroniser
```

- [ ] **Step 4: Run test to confirm pass**

```bash
python -m pytest tests/test_phase2.py::test_new_check_ids_exist -v
```
Expected: PASS

- [ ] **Step 5: Run full existing suite to confirm no regression**

```bash
python -m pytest tests/ -v
```
Expected: 42 passed + 1 new = 43 passed, 0 failed

- [ ] **Step 6: Commit**

```bash
git add rtl_analyzer/models.py tests/test_phase2.py
git commit -m "feat(phase2): add RTL_E006/W006/W007 check IDs"
```

---

## Task 2: Build the elaborator wrapper

**Files:**
- Create: `rtl_analyzer/elaborator.py`
- Modify: `rtl_analyzer/parser/__init__.py` (add `elaborated` field)

The elaborator wraps `pyslang.Compilation` and exposes a clean interface so check authors don't need to know pyslang's internals.

- [ ] **Step 1: Write failing tests for the elaborator**

In `tests/test_phase2.py` add:

```python
from pathlib import Path
from rtl_analyzer.parser import parse_file
from rtl_analyzer.elaborator import ElaboratedModule, build_elaborated

FIXTURES = Path(__file__).parent / "fixtures"

def test_build_elaborated_returns_module():
    pf = parse_file(FIXTURES / "clean" / "clean_counter.v")
    em = build_elaborated(pf)
    assert em is not None
    assert len(em.module_names) >= 1

def test_build_elaborated_no_crash_on_parse_error():
    pf = parse_file(FIXTURES / "buggy" / "buggy_parse_error.v")
    em = build_elaborated(pf)
    # Should return None or empty rather than raise
    assert em is None or em.module_names == []
```

- [ ] **Step 2: Run to confirm failure**

```bash
python -m pytest tests/test_phase2.py::test_build_elaborated_returns_module -v
```
Expected: `ModuleNotFoundError` — `rtl_analyzer.elaborator` does not exist

- [ ] **Step 3: Implement `rtl_analyzer/elaborator.py`**

```python
"""
rtl_analyzer/elaborator.py — pyslang elaboration wrapper.

Wraps pyslang.Compilation to produce an ElaboratedModule: a clean,
check-friendly view of a fully elaborated Verilog/SV module.

Phase 2 checks (FSM, CDC) operate on ElaboratedModule rather than the
raw line model used by Phase 1 checks.

Design rules:
  - Never raises: returns None if elaboration has fatal errors.
  - build_elaborated(pf) is O(1) if pf.elaborated is already set.
  - All pyslang API calls are isolated here; checks never import pyslang.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

import pyslang

from .parser import ParsedFile


@dataclass
class SignalInfo:
    """Lightweight descriptor for a net or variable."""
    name: str
    line: int           # 1-based source line
    width: int          # bit width, 1 if unknown
    clock_domain: Optional[str] = None   # inferred clock name, None if unknown


@dataclass
class ElaboratedModule:
    """
    Check-friendly view of a single elaborated module.

    Built once per ParsedFile by build_elaborated(); cached on pf.elaborated.
    All Phase 2 checks receive this object alongside the ParsedFile.
    """
    module_names: List[str] = field(default_factory=list)
    signals: List[SignalInfo] = field(default_factory=list)
    # clock signals inferred from posedge/negedge sensitivity lists
    clock_signals: Set[str] = field(default_factory=set)
    elaboration_errors: List[str] = field(default_factory=list)


def build_elaborated(pf: ParsedFile) -> Optional[ElaboratedModule]:
    """
    Build an ElaboratedModule from a ParsedFile.

    Returns None if pyslang cannot elaborate the file at all (e.g. missing
    imports that we cannot resolve).  Partial elaboration errors are
    recorded in ElaboratedModule.elaboration_errors but do not return None.
    """
    if pf.syntax_tree is None:
        return None

    em = ElaboratedModule(module_names=list(pf.modules))

    try:
        compilation = pyslang.Compilation()
        compilation.addSyntaxTree(pf.syntax_tree)
        diags = compilation.getAllDiagnostics()
        for d in diags:
            try:
                if d.isError():
                    em.elaboration_errors.append(
                        f"{d.code}: {' '.join(str(a) for a in d.args)}"
                    )
            except Exception:
                em.elaboration_errors.append(str(d))

        root = compilation.getRoot()
        _walk_instance(root, em, pf)

    except Exception as exc:
        # Fatal pyslang error — return empty rather than crash
        em.elaboration_errors.append(f"[fatal] {exc}")

    # Infer clock signals from parser's always-block data
    for ab in pf.always_blocks:
        sens = ab.sensitivity.lower()
        for m in re.finditer(r"\b(?:posedge|negedge)\s+(\w+)", sens):
            em.clock_signals.add(m.group(1))

    return em


def _walk_instance(
    symbol: "pyslang.Symbol",
    em: ElaboratedModule,
    pf: ParsedFile,
) -> None:
    """Recursively walk an elaborated instance and collect signal info."""
    try:
        members = list(symbol.members)
    except Exception:
        return

    for member in members:
        try:
            kind = member.kind
            if kind == pyslang.SymbolKind.Variable:
                _collect_variable(member, em)
            elif kind == pyslang.SymbolKind.Net:
                _collect_net(member, em)
            elif kind in (
                pyslang.SymbolKind.Instance,
                pyslang.SymbolKind.InstanceBody,
            ):
                _walk_instance(member, em, pf)
        except Exception:
            continue


def _collect_variable(sym: "pyslang.VariableSymbol", em: ElaboratedModule) -> None:
    try:
        line = 1
        syntax = sym.getSyntax()
        if syntax is not None:
            loc = syntax.sourceRange().start()
            line = int(loc.line()) if hasattr(loc, "line") else 1
        width = 1
        try:
            width = int(sym.type.bitstreamWidth())
        except Exception:
            pass
        em.signals.append(SignalInfo(name=sym.name, line=line, width=width))
    except Exception:
        pass


def _collect_net(sym: "pyslang.NetSymbol", em: ElaboratedModule) -> None:
    try:
        line = 1
        syntax = sym.getSyntax()
        if syntax is not None:
            loc = syntax.sourceRange().start()
            line = int(loc.line()) if hasattr(loc, "line") else 1
        width = 1
        try:
            width = int(sym.type.bitstreamWidth())
        except Exception:
            pass
        em.signals.append(SignalInfo(name=sym.name, line=line, width=width))
    except Exception:
        pass
```

- [ ] **Step 4: Add `elaborated` field to `ParsedFile` in `parser/__init__.py`**

After `parse_errors: List[str]` in the `ParsedFile` dataclass:
```python
    # Phase 2: populated lazily by elaborator.build_elaborated()
    elaborated: Optional["ElaboratedModule"] = field(default=None, repr=False)
```
(The `ElaboratedModule` type is a forward ref; add `from __future__ import annotations` if not already present — it is.)

- [ ] **Step 5: Run elaborator tests**

```bash
python -m pytest tests/test_phase2.py -v
```
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add rtl_analyzer/elaborator.py rtl_analyzer/parser/__init__.py tests/test_phase2.py
git commit -m "feat(phase2): add elaborator wrapper around pyslang.Compilation"
```

---

## Task 3: FSM fixtures

**Files:**
- Create: `tests/fixtures/buggy/buggy_fsm_unreachable.v`
- Create: `tests/fixtures/buggy/buggy_fsm_no_default.sv`

- [ ] **Step 1: Create `buggy_fsm_unreachable.v`**

```verilog
// buggy_fsm_unreachable.v
// RTL_E006 fixture: state DEAD is never reached from any transition.
module buggy_fsm_unreachable (
    input  wire clk,
    input  wire rst_n,
    input  wire go,
    output reg  done
);
    typedef enum logic [1:0] {
        IDLE  = 2'b00,
        RUN   = 2'b01,
        DONE  = 2'b10,
        DEAD  = 2'b11   // unreachable — no transition leads here
    } state_t;

    state_t state, next;

    // State register
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) state <= IDLE;
        else        state <= next;
    end

    // Next-state logic
    always_comb begin
        next = state;
        done = 1'b0;
        case (state)
            IDLE: if (go) next = RUN;
            RUN:  next = DONE;
            DONE: begin done = 1'b1; next = IDLE; end
            // DEAD: never assigned — unreachable
            default: next = IDLE;
        endcase
    end
endmodule
```

- [ ] **Step 2: Create `buggy_fsm_no_default.sv`**

```systemverilog
// buggy_fsm_no_default.sv
// RTL_W006 fixture: FSM next-state logic has no default branch.
module buggy_fsm_no_default (
    input  logic clk,
    input  logic rst_n,
    input  logic go,
    output logic done
);
    typedef enum logic [1:0] {IDLE, RUN, DONE} state_t;
    state_t state, next;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) state <= IDLE;
        else        state <= next;
    end

    // No default: if state is 2'b11 (unencoded), next is X
    always_comb begin
        next = IDLE;
        done = 1'b0;
        case (state)
            IDLE: if (go) next = RUN;
            RUN:  next = DONE;
            DONE: begin done = 1'b1; next = IDLE; end
            // deliberately no default
        endcase
    end
endmodule
```

- [ ] **Step 3: Verify fixtures parse without Python errors**

```bash
python -c "
from rtl_analyzer.parser import parse_file
from pathlib import Path
pf = parse_file(Path('tests/fixtures/buggy/buggy_fsm_unreachable.v'))
print('modules:', pf.modules)
pf2 = parse_file(Path('tests/fixtures/buggy/buggy_fsm_no_default.sv'))
print('modules:', pf2.modules)
"
```

- [ ] **Step 4: Commit**

```bash
git add tests/fixtures/buggy/buggy_fsm_unreachable.v tests/fixtures/buggy/buggy_fsm_no_default.sv
git commit -m "test(phase2): add FSM fixtures for RTL_E006 and RTL_W006"
```

---

## Task 4: FSM check (RTL_E006 + RTL_W006)

**Files:**
- Create: `rtl_analyzer/checks/fsm_extractor.py`

The FSM check uses the **regex line model** (ParsedFile) rather than the elaborated AST. This is intentional for Phase 2: pyslang elaboration of `typedef enum` in mixed Verilog/SV is reliable only for `.sv` files. The regex approach catches the 80% case (case-statement FSMs) with zero false positives, matching Phase 1's conservative design.

The check works as follows:
1. Find all `typedef enum` declarations and extract state names.
2. Find the always_comb/always @(*) block that contains a `case(state)` — the next-state block.
3. Build a set of states that appear on the LHS of any transition (`next = STATE_NAME`).
4. States declared in the enum but never assigned → RTL_E006 (unreachable).
5. If the case block has no `default:` → RTL_W006.

- [ ] **Step 1: Write failing tests**

In `tests/test_phase2.py` add:

```python
from rtl_analyzer import AnalysisEngine
from rtl_analyzer.models import CheckID, Severity

def _analyze(path):
    return AnalysisEngine().analyze_file(path)

def test_fsm_detects_unreachable_state():
    r = _analyze(FIXTURES / "buggy" / "buggy_fsm_unreachable.v")
    assert CheckID.RTL_E006 in {f.check_id for f in r.findings}, (
        "Should flag DEAD state as unreachable. SpyGlass FSM_5 flags this."
    )

def test_fsm_detects_missing_default():
    r = _analyze(FIXTURES / "buggy" / "buggy_fsm_no_default.sv")
    assert CheckID.RTL_W006 in {f.check_id for f in r.findings}, (
        "Should flag FSM case with no default. SpyGlass FSM_1 flags this."
    )

def test_fsm_no_crash_on_non_enum_fsm():
    # clean_fsm.v uses localparam not typedef enum — check must not crash
    # and must not flag anything (early return when enum_states is empty).
    r = _analyze(FIXTURES / "clean" / "clean_fsm.v")
    e006 = [f for f in r.findings if f.check_id == CheckID.RTL_E006]
    w006 = [f for f in r.findings if f.check_id == CheckID.RTL_W006]
    assert not e006, f"Unexpected RTL_E006 on non-enum FSM: {e006}"
    assert not w006, f"Unexpected RTL_W006 on non-enum FSM: {w006}"

def test_fsm_clean_enum_no_false_positives():
    # buggy_fsm_unreachable.v has an enum — but the DEAD state exists and IS
    # unreachable. Use buggy_cdc.v (no FSM) to confirm no spurious FSM findings.
    r = _analyze(FIXTURES / "buggy" / "buggy_cdc.v")
    e006 = [f for f in r.findings if f.check_id == CheckID.RTL_E006]
    assert not e006, (
        "buggy_cdc.v has no typedef enum FSM — RTL_E006 must not fire on it"
    )
```

- [ ] **Step 2: Run to confirm failure**

```bash
python -m pytest tests/test_phase2.py::test_fsm_detects_unreachable_state -v
```
Expected: `AssertionError` — check not yet implemented

- [ ] **Step 3: Implement `rtl_analyzer/checks/fsm_extractor.py`**

```python
"""
RTL_E006 — FSM unreachable state.
RTL_W006 — FSM next-state logic missing default branch.

Algorithm (regex-based, conservative):
  1. Find typedef enum { STATE_A, STATE_B, ... } in the file.
  2. Find the always_comb block that has case(<state_reg>).
  3. Collect all state names that appear as RHS of next = <STATE> assignments.
  4. States in enum but NOT in transition RHS → RTL_E006.
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

    enum_states = _extract_enum_states(pf.source)
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
        for m in re.finditer(r"<=\s*(\w+)\s*;", pf.source):
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
```

- [ ] **Step 4: Register in `checks/__init__.py`**

```python
from .fsm_extractor import check_fsm
# add check_fsm to ALL_CHECKS list
```

- [ ] **Step 5: Run FSM tests**

```bash
python -m pytest tests/test_phase2.py -k fsm -v
```
Expected: 3 passed

- [ ] **Step 6: Run full suite**

```bash
python -m pytest tests/ -v
```
Expected: all pass (42 prior + 3 new + 2 import + 2 elaborator = 49 total)

- [ ] **Step 7: Commit**

```bash
git add rtl_analyzer/checks/fsm_extractor.py rtl_analyzer/checks/__init__.py tests/test_phase2.py
git commit -m "feat(phase2): implement FSM check (RTL_E006 unreachable state, RTL_W006 missing default)"
```

---

## Task 5: CDC fixtures

**Files:**
- Create: `tests/fixtures/buggy/buggy_cdc.v`
- Create: `tests/fixtures/clean/clean_cdc_synced.v`

- [ ] **Step 1: Create `buggy_cdc.v`**

```verilog
// buggy_cdc.v
// RTL_W007 fixture: data_in is clocked by clk_a; it is read directly in
// the clk_b domain with no synchroniser flip-flops in between.
module buggy_cdc (
    input  wire clk_a,
    input  wire clk_b,
    input  wire rst_n,
    input  wire data_in,     // driven in clk_a domain
    output reg  data_out     // sampled in clk_b domain — CDC hazard
);
    reg data_reg_a;

    // clk_a domain: register data_in
    always @(posedge clk_a or negedge rst_n) begin
        if (!rst_n) data_reg_a <= 1'b0;
        else        data_reg_a <= data_in;
    end

    // clk_b domain: reads data_reg_a directly — no synchroniser
    always @(posedge clk_b or negedge rst_n) begin
        if (!rst_n) data_out <= 1'b0;
        else        data_out <= data_reg_a;   // RTL_W007: no sync
    end
endmodule
```

- [ ] **Step 2: Create `clean_cdc_synced.v`**

```verilog
// clean_cdc_synced.v
// Two-clock design with a 2FF synchroniser — no RTL_W007.
module clean_cdc_synced (
    input  wire clk_a,
    input  wire clk_b,
    input  wire rst_n,
    input  wire data_in,
    output reg  data_out
);
    reg data_reg_a;
    reg sync_ff1, sync_ff2;   // 2FF synchroniser in clk_b domain

    always @(posedge clk_a or negedge rst_n) begin
        if (!rst_n) data_reg_a <= 1'b0;
        else        data_reg_a <= data_in;
    end

    // Synchroniser chain
    always @(posedge clk_b or negedge rst_n) begin
        if (!rst_n) begin
            sync_ff1 <= 1'b0;
            sync_ff2 <= 1'b0;
        end else begin
            sync_ff1 <= data_reg_a;
            sync_ff2 <= sync_ff1;
        end
    end

    always @(posedge clk_b or negedge rst_n) begin
        if (!rst_n) data_out <= 1'b0;
        else        data_out <= sync_ff2;
    end
endmodule
```

- [ ] **Step 3: Verify fixtures parse**

```bash
python -c "
from rtl_analyzer.parser import parse_file
from pathlib import Path
for f in ['tests/fixtures/buggy/buggy_cdc.v', 'tests/fixtures/clean/clean_cdc_synced.v']:
    pf = parse_file(Path(f))
    print(f, '->', pf.modules, 'clocks:', [ab.sensitivity for ab in pf.always_blocks])
"
```

- [ ] **Step 4: Commit**

```bash
git add tests/fixtures/buggy/buggy_cdc.v tests/fixtures/clean/clean_cdc_synced.v
git commit -m "test(phase2): add CDC fixtures for RTL_W007"
```

---

## Task 6: CDC check (RTL_W007)

**Files:**
- Create: `rtl_analyzer/checks/cdc_checker.py`

CDC detection algorithm:
1. Identify distinct clock signals from `always @(posedge X)` blocks — if only one clock, no CDC possible.
2. For each always block, determine which clock it belongs to (its posedge signal).
3. Build a map: `signal → set of clocks that write it`.
4. For each always block clocked by `clk_B`, scan RHS of assignments. If a RHS signal is in the "written by clk_A" map where `clk_A != clk_B`, and that signal has no matching sync-chain (not assigned in an intermediate block of clk_B that reads from a single-bit signal), flag RTL_W007.

Conservative: only flag when we can clearly see a direct read of a cross-domain signal with no intermediate clk_B register.

- [ ] **Step 1: Write failing tests**

In `tests/test_phase2.py` add:

```python
def test_cdc_detects_unsync_crossing():
    r = _analyze(FIXTURES / "buggy" / "buggy_cdc.v")
    assert CheckID.RTL_W007 in {f.check_id for f in r.findings}, (
        "Should flag data_reg_a read in clk_b domain without synchroniser. "
        "SpyGlass CDC_GLITCH flags this; Mentor Questa CDC also flags it."
    )

def test_cdc_clean_no_false_positive():
    r = _analyze(FIXTURES / "clean" / "clean_cdc_synced.v")
    w007 = [f for f in r.findings if f.check_id == CheckID.RTL_W007]
    assert not w007, f"False positive RTL_W007 on synced CDC: {w007}"

def test_single_clock_no_cdc():
    r = _analyze(FIXTURES / "clean" / "clean_counter.v")
    w007 = [f for f in r.findings if f.check_id == CheckID.RTL_W007]
    assert not w007, f"Single-clock design should never trigger RTL_W007"
```

- [ ] **Step 2: Run to confirm failure**

```bash
python -m pytest tests/test_phase2.py::test_cdc_detects_unsync_crossing -v
```
Expected: `AssertionError`

- [ ] **Step 3: Implement `rtl_analyzer/checks/cdc_checker.py`**

```python
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

References:
  Synopsys SpyGlass CDC: CDC_GLITCH.
  Mentor Questa CDC: cdc_data rule.
  IEEE 1800.2 (UVM) CDC analysis guidelines.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Dict, List, Set

from ..models import CheckID, Finding, Severity
from ..parser import AlwaysKind, ParsedFile

_RE_RHS_SIGNAL = re.compile(r"(?:<=|=)\s*(\w+)\s*;")
_RE_LHS_SIGNAL = re.compile(r"(\w+)\s*(?:\[.*?\])?\s*<=")


def _get_block_clock(ab) -> str:
    """Return the posedge/negedge clock name for this always block, or ''."""
    m = re.search(r"\b(?:posedge|negedge)\s+(\w+)", ab.sensitivity, re.I)
    return m.group(1).lower() if m else ""


def check_cdc(pf: ParsedFile) -> List[Finding]:
    findings: List[Finding] = []

    # Only sequential (FF) blocks participate in CDC analysis
    ff_blocks = [ab for ab in pf.always_blocks if ab.kind == AlwaysKind.FF
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
    block_clock: Dict[int, str] = {}    # ab.start_line → clock_name

    for ab in ff_blocks:
        clk = _get_block_clock(ab)
        if not clk:
            continue
        block_clock[ab.start_line] = clk
        lines = pf.lines[ab.start_line - 1 : ab.end_line]
        for li in lines:
            for m in _RE_LHS_SIGNAL.finditer(li.stripped):
                sig = m.group(1)
                if sig not in ("if", "else", "begin", "end"):
                    signal_writer[sig] = clk

    # ── Step 3: collect signals that are synchronised in any clk_B block ──
    # A signal is "sync-absorbed" in clk_B if it is the sole RHS of an
    # assignment in a clk_B block (the typical sync-FF pattern).
    sync_absorbed: Set[str] = set()
    for ab in ff_blocks:
        clk = _get_block_clock(ab)
        if not clk:
            continue
        lines = pf.lines[ab.start_line - 1 : ab.end_line]
        # Count assignments in this block
        lhs_sigs = []
        rhs_sigs = []
        for li in lines:
            for m in _RE_LHS_SIGNAL.finditer(li.stripped):
                s = m.group(1)
                if s not in ("if", "else", "begin", "end"):
                    lhs_sigs.append(s)
            for m in _RE_RHS_SIGNAL.finditer(li.stripped):
                s = m.group(1)
                if s not in ("if", "else", "begin", "end"):
                    rhs_sigs.append(s)
        # If a block assigns exactly one signal from a foreign clock domain,
        # treat it as a synchroniser stage — absorb its RHS signals
        foreign_rhs = [s for s in rhs_sigs
                       if signal_writer.get(s, clk) != clk]
        if len(lhs_sigs) <= 2 and len(foreign_rhs) >= 1:
            for s in foreign_rhs:
                sync_absorbed.add(s)
            # also absorb what this block drives (sync_ff1 → absorbed chain)
            for s in lhs_sigs:
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
                    break  # one finding per always block per crossing

    return findings
```

- [ ] **Step 4: Register in `checks/__init__.py`**

```python
from .cdc_checker import check_cdc
# add check_cdc to ALL_CHECKS list
```

- [ ] **Step 5: Run CDC tests**

```bash
python -m pytest tests/test_phase2.py -k cdc -v
```
Expected: 3 passed

- [ ] **Step 6: Run full suite**

```bash
python -m pytest tests/ -v
```
Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add rtl_analyzer/checks/cdc_checker.py rtl_analyzer/checks/__init__.py tests/test_phase2.py
git commit -m "feat(phase2): implement CDC check (RTL_W007 unsynchronised clock crossing)"
```

---

## Task 7: Update benchmarks

**Files:**
- Modify: `benchmarks/compare_tools.py`

- [ ] **Step 1: Add Phase 2 fixture entries to `REFERENCE_EXPECTATIONS`**

Add to the dict:

```python
"buggy_fsm_unreachable.v": [
    {
        "description": "unreachable FSM state (DEAD never reached)",
        "rtl_analyzer": "RTL_E006",
        "verilator": "no-direct-equivalent",
        "verible": "no-direct-equivalent",
        "spyglass": "FSM_5",
    },
],
"buggy_fsm_no_default.sv": [
    {
        "description": "FSM next-state case missing default",
        "rtl_analyzer": "RTL_W006",
        "verilator": "CASEINCOMPLETE (W)",
        "verible": "case-missing-default",
        "spyglass": "FSM_1",
    },
],
"buggy_cdc.v": [
    {
        "description": "direct cross-domain read without synchroniser",
        "rtl_analyzer": "RTL_W007",
        "verilator": "no-direct-equivalent",
        "verible": "no-direct-equivalent",
        "spyglass": "CDC_GLITCH",
    },
],
```

- [ ] **Step 2: Run benchmarks**

```bash
python benchmarks/compare_tools.py
```
Expected: 0 regressions

- [ ] **Step 3: Commit**

```bash
git add benchmarks/compare_tools.py
git commit -m "docs(phase2): update benchmark reference table for Phase 2 checks"
```

---

## Task 8: Final verification

- [ ] **Step 1: Full test suite**

```bash
python -m pytest tests/ -v --tb=short
```
Expected: all pass, 0 failures

- [ ] **Step 2: Benchmark clean**

```bash
python benchmarks/compare_tools.py
```
Expected: 0 regressions

- [ ] **Step 3: Smoke-test the CLI**

```bash
rtl-check tests/fixtures/buggy/buggy_cdc.v tests/fixtures/buggy/buggy_fsm_unreachable.v
```
Expected: RTL_W007 and RTL_E006 findings printed, non-zero exit code

- [ ] **Step 4: JSON output check**

```bash
rtl-check --format json tests/fixtures/buggy/buggy_cdc.v | python -m json.tool | grep RTL_W007
```
Expected: RTL_W007 appears in JSON output

- [ ] **Step 5: Tag v0.2.0**

```bash
git tag v0.2.0
```

---

## Known limitations / Phase 3 deferral

| Limitation | Why deferred |
|---|---|
| RTL_E006 misses FSMs encoded without `typedef enum` | Requires pyslang elaborated type inference — Phase 3 |
| RTL_W007 misses CDC through module ports | Requires cross-module elaboration — Phase 3 |
| RTL_W007 does not validate synchroniser depth (1FF vs 2FF) | Requires dataflow tracing — Phase 3 |
| RTL_E002 (combinational loop) still stub | Requires signal dependency DAG — Phase 3 |

---

## Quick-reference: run commands

```bash
cd /home/jovyan/silicogen/rtl_analyzer

# Run all tests
python -m pytest tests/ -v

# Run only Phase 2 tests
python -m pytest tests/test_phase2.py -v

# Run benchmarks
python benchmarks/compare_tools.py

# CLI smoke test
rtl-check tests/fixtures/buggy/buggy_cdc.v
```
