# Tooling Insights — I²C Controller

**Purpose**: Capture what was painful, repetitive, or error-prone in each phase, and propose concrete tools/automation to improve future work.

---

## Methodology Decision Analysis: Direct SV vs UVM

**Date**: 2026-03-15
**Decision**: Upgraded verification from Direct SystemVerilog to UVM 1.2

### Research Findings (Web Search)

| Source | Key Finding |
|--------|-------------|
| RIT Thesis | UVM verification of I²C master with constrained random testing |
| IJSR Paper | 95.07% total coverage achieved with UVM (100% assertion, 90.15% functional) |
| IJCSMC Paper | UVM enables self-checking, reusable, coverage-driven verification |
| Industry papers | UVM is 90%+ of ASIC verification methodology choice |
| Verification Academy | "70% of design effort goes to verification" |

### Original Plan vs Industry Standard

| Metric | Original Plan (Direct SV) | Industry Standard (UVM) |
|--------|---------------------------|-------------------------|
| Test methodology | 20 directed tests | Constrained random + directed |
| Test count | 20 manual | 1000+ automated |
| Coverage tracking | Manual | Built-in automated |
| Reusability | Low | High (standard components) |
| Team scalability | Poor | Excellent (standard patterns) |

### Decision Rationale

**Why upgrade to UVM**:
1. **Industry alignment**: 90%+ of ASIC projects use UVM
2. **Coverage-driven**: Automated coverage tracking vs manual
3. **Random testing**: Discovers bugs directed tests miss
4. **Reusability**: UVM environment portable to future projects
5. **Professional development**: Learning industry-standard methodology

**Trade-offs accepted**:
1. **Setup time**: +2-3 days for UVM infrastructure
2. **Learning curve**: UVM is complex
3. **Code volume**: 2000-3000 lines vs 1400-2350

### Impact on Project

| Aspect | Before | After |
|--------|--------|-------|
| Verification lines | 1400-2350 | 2000-3000 |
| Phase 3 duration | 4-7 days | 5-8 days |
| Total project | 12-21 days | 14-22 days |
| Test scenarios | 20 | 1000+ |
| Coverage confidence | Manual estimate | Measured 95%+ |

### Lessons for Future Projects

1. **Start with methodology research**: Web search industry standards before committing
2. **Consider long-term value**: UVM investment pays off across multiple projects
3. **Coverage targets must be measurable**: "95%" needs automated collection
4. **Test count matters**: 20 tests is far below industry standard for production IP

---

## Phase 0: Environment & Infrastructure — Reflection & Tooling Ideas

**Date**: 2026-03-15
**Phase Duration**: 30 minutes

### 1. What Was Harder Than Expected?

- Verifying tool availability required checking 5+ tools with different command syntaxes
- Creating consistent documentation templates from scratch was manual
- The Makefile needed careful path configuration for non-standard tool locations

### 2. What Was Repetitive or Error-Prone?

- Creating multiple .md files with similar header/footer structure
- Checking tool versions with different version flags and output formats
- Maintaining consistent status tracking between TODO.md and actual progress

### 3. What Information Was Hard to See or Understand?

- Tool version compatibility (which QuestaSim version supports which SystemVerilog features)
- Whether all required PDK paths exist and are correctly configured

### 4. Proposed Tools & Automation

#### Tool Idea: Environment Verification Script
- **Problem it solves**: Manual tool checking is tedious and error-prone
- **What it would do**: Single script that checks all tools, versions, paths, and reports a pass/fail matrix
- **Input**: Tool configuration (paths, minimum versions)
- **Output**: Formatted table of tool status, missing dependencies, version warnings
- **Effort to build**: Small (2-4 hours)
- **Impact**: Saves 10-15 minutes per project setup, catches missing tools early

#### Tool Idea: Project Scaffolding Generator
- **Problem it solves**: Creating consistent directory structures and documentation templates
- **What it would do**: CLI tool that creates project structure from a template (dirs, Makefile, docs skeleton)
- **Input**: Project name, target technology (FPGA/ASIC), simulator choice
- **Output**: Complete directory structure with Makefile, placeholder docs, .gitignore
- **Effort to build**: Small (2-4 hours)
- **Impact**: Saves 30 minutes per new project, ensures consistency across projects

### 5. If I Could Restart This Phase With Any Tool in the World, What Would It Be?

A "project wizard" that takes high-level requirements (I²C controller, QuestaSim, Yosys, sky130) and generates the complete project skeleton including Makefile with correct tool paths, documentation templates with project-specific placeholders, and initial TODO tracking.

---

## Phase 1: Architecture Documentation — Reflection & Tooling Ideas

**Date**: 2026-03-15
**Phase Duration**: 45 minutes

### 1. What Was Harder Than Expected?

- Ensuring consistency across 6 architecture documents (register map, state machines, interfaces must align)
- Creating timing diagrams in ASCII art is time-consuming and hard to modify
- State machine documentation requires careful cross-referencing with detection logic

### 2. What Was Repetitive or Error-Prone?

- Documenting the same signals in multiple places (interfaces.md vs state_machines.md)
- Manually calculating prescaler values for different I²C speeds
- Keeping register bit definitions consistent between interfaces.md and future RTL

### 3. What Information Was Hard to See or Understand?

- How clock stretching interacts with the bit controller FSM states
- Timing relationships between the 4-phase clock enables and I²C bus timing parameters
- Arbitration detection window alignment with SCL HIGH phase

### 4. Proposed Tools & Automation

#### Tool Idea: Register Map Compiler
- **Problem it solves**: Register definitions must be consistent across docs, RTL, testbench, and C headers
- **What it would do**: Parse YAML register specification, generate docs (markdown table), RTL (register file module), testbench access tasks, and C header file
- **Input**: YAML file defining registers (name, offset, bits, access, reset value)
- **Output**: interfaces.md register table, i2c_register_file.v skeleton, tb register access tasks, i2c_regs.h
- **Effort to build**: Medium (4-8 hours)
- **Impact**: Eliminates register definition inconsistencies, saves hours on any change

#### Tool Idea: FSM State Diagram Generator
- **Problem it solves**: ASCII state diagrams are hard to create and maintain
- **What it would do**: Parse FSM definition (states, transitions, conditions), generate Mermaid or Graphviz diagram embedded in markdown
- **Input**: State table in YAML or simple text format
- **Output**: Renderable diagram embedded in state_machines.md
- **Effort to build**: Small (2-4 hours)
- **Impact**: Clearer state machine documentation, easy to update

#### Tool Idea: Doc-vs-RTL Consistency Checker
- **Problem it solves**: Docs and RTL drift apart over time
- **What it would do**: Parse docs (port tables, register maps) and RTL (module ports, parameter lists), flag mismatches
- **Input**: docs/*.md and rtl/*.v files
- **Output**: List of inconsistencies (missing ports, wrong widths, undefined signals)
- **Effort to build**: Medium (4-8 hours)
- **Impact**: Catches documentation bugs before they become RTL bugs

### 5. If I Could Restart This Phase With Any Tool in the World, What Would It Be?

An "architecture workbench" — an interactive tool where I define signals, registers, and state machines once, and it auto-generates all documentation with timing diagrams, state transition tables, and cross-references. Changes propagate automatically. Think of it like a schematic editor but for documentation.

---

## Phase 2: RTL Implementation — Reflection & Tooling Ideas

**Date**: 2026-03-15
**Phase Duration**: 2 hours

### 1. What Was Harder Than Expected?

- **Finding subtle bugs without simulation**: The `arb_lost` sticky register bug would have caused permanent controller lockup but was not caught by compilation
- **Cross-tool compatibility**: QuestaSim compiled code that Yosys rejected (missing port), revealing different strictness levels
- **Spec interpretation**: BUSY flag semantics required careful reading - "bus busy" vs "transfer in progress" are different concepts
- **Signal lifecycle decisions**: Determining where state should live (sticky in register file vs pulse in FSM) was not obvious

### 2. What Was Repetitive or Error-Prone?

- Writing similar FSM state declarations across multiple modules
- Checking reset values match documentation for every register
- Manually verifying port connections between modules
- Cross-referencing state machine docs with RTL implementation

### 3. What Information Was Hard to See or Understand?

- Which signals need to be registered vs combinational across state boundaries
- Where "stickiness" should live for flags (register file vs FSM)
- Clock domain crossing requirements for async bus signals
- Open-drain bus modeling conventions (_o, _i, _oen)

### 4. Proposed Tools & Automation

#### Tool Idea: RTL vs Doc Consistency Checker
- **Problem it solves**: Bugs like missing ports, wrong reset values, wrong bit positions slip through
- **What it would do**: Parse docs (port tables, register maps, state encodings) and RTL, flag mismatches
- **Input**: `docs/interfaces.md`, `docs/state_machines.md` and `rtl/*.v` files
- **Output**: Table of inconsistencies: missing ports, wrong widths, reset value mismatches, undefined states
- **Effort to build**: Medium (4-8 hours)
- **Impact**: Would have caught BUG-001, BUG-002, BUG-003, BUG-006 before "completion"

#### Tool Idea: FSM State Linting
- **Problem it solves**: Sticky flags in FSMs, missing default cases, unlatched signals across states
- **What it would do**: Analyze FSM code for common patterns that indicate bugs (sticky registers without clear, signals computed in state A but used in state B without latch)
- **Input**: RTL files with FSM modules
- **Output**: Warning messages with line numbers for potential FSM bugs
- **Effort to build**: Medium (8-16 hours) - requires parsing always blocks
- **Impact**: Would have caught BUG-003 (arb_lost sticky without clear)

#### Tool Idea: Dual-Compiler Verification Runner
- **Problem it solves**: Different simulators/synthesizers have different strictness levels
- **What it would do**: Run both QuestaSim vlog AND Yosys on RTL, report all errors/warnings from both
- **Input**: RTL file list
- **Output**: Combined error report with source attribution
- **Effort to build**: Small (1-2 hours)
- **Impact**: Would have caught BUG-006 immediately

### 5. If I Could Restart This Phase With Any Tool in the World, What Would It Be?

A "RTL correctness dashboard" that:
1. Shows a matrix of all registers and their reset values vs documentation
2. Highlights signals that cross state boundaries without registration
3. Runs multiple compilers and aggregates their outputs
4. Generates FSM state transition diagrams from RTL for visual verification
5. Checks clock domain crossings for proper synchronizers

This would have caught 5 of 7 bugs before any simulation.

### 6. Root Cause Analysis: Why Did Bugs Slip Through?

The fundamental issue was **declaring completion without verification**. The RTL compiled with 0 errors/warnings in QuestaSim, which was incorrectly interpreted as "correct". Key missing steps:

1. **No simulation**: Functional bugs cannot be caught by compilation alone
2. **No assertions**: SVA assertions would have caught spec violations
3. **No cross-tool verification**: Yosys caught what QuestaSim missed
4. **No systematic review**: The checklist approach applied in this session found bugs missed earlier

---

## Phase 3: Verification — Reflection & Tooling Ideas

**Date**: 2026-03-15
**Phase Duration**: 3 hours

### 1. What Was Harder Than Expected?

- **UVM DPI library**: Required manual compilation of uvm_dpi.so - QuestaSim doesn't auto-load it
- **Interface port types**: QuestaSim requires `input bit` not `input wire` for virtual interfaces
- **Reserved keywords**: Coverage bin names `small`, `medium` are reserved in SystemVerilog
- **Package vs includes**: Files must be `include`d in package, not have their own `import uvm_pkg::*`
- **Queue vs dynamic array**: `uvm_field_array_int` doesn't work with queues (`[$]`)

### 2. What Was Repetitive or Error-Prone?

- Adding `import uvm_pkg::*; `include "uvm_macros.svh"` to every file (solved by package include)
- Fixing interface port types multiple times
- Coverage bin naming conflicts with reserved keywords

### 3. What Information Was Hard to See or Understand?

- Which UVM components need to be in package vs compiled separately
- Virtual interface binding requirements for QuestaSim
- DPI library compilation requirements

### 4. Proposed Tools & Automation

#### Tool Idea: UVM Project Generator
- **Problem it solves**: UVM boilerplate is error-prone (imports, packages, interface types)
- **What it would do**: Generate correct UVM testbench skeleton with proper QuestaSim compatibility
- **Input**: DUT interface specification
- **Output**: Complete UVM environment with correct imports, package structure
- **Effort to build**: Medium (8-16 hours)
- **Impact**: Eliminates 50+ compilation errors from boilerplate mistakes

#### Tool Idea: QuestaSim UVM Launcher
- **Problem it solves**: Need to compile DPI library and pass -sv_lib every time
- **What it would do**: Auto-detect if DPI library exists, compile if needed, launch vsim correctly
- **Input**: Test name
- **Output**: Runs simulation with correct flags
- **Effort to build**: Small (2-4 hours)
- **Impact**: One-command UVM test execution

### 5. If I Could Restart This Phase With Any Tool in the World, What Would It Be?

A "UVM workbench" that:
1. Generates all boilerplate correctly for QuestaSim
2. Auto-compiles DPI libraries
3. Provides a unified test runner
4. Catches reserved keyword conflicts before compilation

### 6. Key Learnings

- Always compile UVM DPI library before first simulation
- Use `input bit` for virtual interface ports in QuestaSim
- Use package `include` instead of per-file imports
- Avoid reserved keywords in coverage bins (add prefix like `cb_`)
- Run with `-64` flag for 64-bit QuestaSim

---

## Phase 3.5: Debugging Methodology — Critical Lessons (2026-03-16)

**Date**: 2026-03-16
**Session Duration**: 4+ hours (wasted) vs 18 minutes (successful)

### 1. What Happened: Two Approaches, Two Outcomes

| Metric | My Approach (Failed) | Claude Code (Successful) |
|--------|---------------------|-------------------------|
| Time spent | 4+ hours | 18 minutes |
| Changes made | 10+ slave rewrites | 7 targeted RTL fixes |
| Root causes found | 3/7 (slave only) | 7/7 (4 RTL + 3 slave) |
| Tests passing | 1/5 (arb only) | 5/5 (all with data integrity) |

### 2. The Critical Difference: Systematic vs Random Debugging

**Claude Code's Approach (Systematic):**
```
Tests fail
  ↓
Check scoreboard: "Writes: 0 | Reads: 0" (vacuously passing)
  ↓
Why? All transactions have error=1
  ↓
Why? DUT reports NACK when slave sends ACK
  ↓
Why? Slave releases SDA on scl_rise, DUT samples at cnt2 (20 cycles later)
  ↓
FIX: Slave holds SDA=0 through SCL HIGH
```

**My Approach (Guess-and-Check):**
```
Tests fail
  ↓
"Slave must be wrong"
  ↓
Rewrite slave #1 (async → sync)
  ↓
Still fails → Rewrite slave #2 (different FSM)
  ↓
Still fails → Rewrite slave #3...
```

### 3. What Information Was Hard to See

| Bug | Why I Missed It | How Claude Found It |
|-----|----------------|---------------------|
| `dout_reg` never captured | Didn't trace from scoreboard backward | Checked why error=1 on all transactions |
| `cmd_ack_r` not latched | Assumed testbench was the problem | Traced ACK pulse lifecycle |
| BYTE_ACK did STOP not READ | Didn't understand protocol semantics | Knew read-ACK requires WRITE operation |
| Read-ACK direction wrong | Confused master/slave roles | Understood I2C ACK/NACK flow |

### 4. Root Cause: Why I Wasted 4 Hours

1. **Didn't follow evidence** — Assumed problem location instead of tracing
2. **Didn't ask "WHY?"** — Made changes without understanding root cause
3. **Didn't check RTL first** — Blamed testbench while DUT had bugs
4. **Didn't understand protocol** — I2C ACK/NACK direction unclear

### 5. Proposed Tools & Automation

#### Tool Idea: Backward Trace Debugger
- **Problem it solves**: Hard to trace from symptom (test fail) to root cause (RTL bug)
- **What it would do**: Given a failing assertion, automatically trace backward through signal dependencies to find source
- **Input**: Failing signal + cycle number
- **Output**: Dependency tree showing where value originated
- **Effort to build**: Large (requires simulator integration)
- **Impact**: Would have found `dout_reg` bug in minutes, not hours

#### Tool Idea: Protocol-Aware Assertion Generator
- **Problem it solves**: Missing protocol semantics (e.g., "read-ACK uses WRITE")
- **What it would do**: Generate SVA assertions from protocol spec (I2C, AXI, etc.)
- **Input**: Protocol type + DUT interface
- **Output**: SVA assertions for ACK timing, direction, sequencing
- **Effort to build**: Medium (4-8 hours per protocol)
- **Impact**: Would have caught BYTE_ACK sequencing bug immediately

#### Tool Idea: "Why Is This 1?" Analyzer
- **Problem it solves**: Understanding why a signal has unexpected value
- **What it would do**: For any signal at any cycle, show: (1) what drove it, (2) what conditions were true, (3) alternative values it could have had
- **Input**: Signal name + cycle
- **Output**: Causal explanation with waveform snippet
- **Effort to build**: Medium (can use existing simulator features)
- **Impact**: Would have shown why `error=1` on every transaction

### 6. If I Could Restart This Debug Session With Any Tool

A **"Systematic Debug Assistant"** that enforces the debugging discipline:

1. **Forces backward tracing**: "Show me the scoreboard output. Now show me why error=1."
2. **Asks "WHY?" at each step**: "Why does DUT report NACK? Show me the ACK sampling waveform."
3. **Checks RTL before testbench**: "Before rewriting slave, verify DUT receives ACK correctly."
4. **Validates protocol understanding**: "For read transactions, who sends ACK? Master or slave?"

This tool would have prevented 4 hours of wasted time by enforcing systematic debugging discipline.

### 7. Key Learnings for Future Debug Sessions

| Lesson | Application |
|--------|-------------|
| **Start from failure, trace backward** | Never assume problem location; follow evidence |
| **Ask "WHY?" at least 5 times** | Each answer reveals deeper root cause |
| **Check RTL before testbench** | DUT bugs are more likely than testbench bugs |
| **Understand protocol semantics** | I2C: master sends ACK after READ, slave sends ACK after WRITE |
| **One fix at a time** | Don't make multiple changes before verifying |
| **Verify after each fix** | Run tests, check scoreboard, confirm improvement |
| **Clean state validation** | Always verify from `make clean` before declaring complete |

### 8. Clean State Validation Checklist (Added 2026-03-16)

Before declaring any phase complete:

1. Run `make clean` to remove all build artifacts
2. Run `make all-tests` from clean state
3. Verify ALL tests pass (not just one)
4. Check scoreboard shows actual data checks (not vacuous pass)
5. Verify data integrity (0 mismatches)
6. Document any new bugs in BUG_LOG.md
7. Update TODO.md with current status

This checklist prevents "works on my machine" syndrome and ensures reproducibility.

### 9. Updated Prioritized Tool Ideas

| Rank | Tool Idea | Effort | Impact | Would Have Caught |
|------|-----------|--------|--------|-------------------|
| 1 | **Backward Trace Debugger** | Large | Critical | All 7 bugs in <30 min |
| 2 | **"Why Is This 1?" Analyzer** | Medium | Critical | dout_reg, cmd_ack_r bugs |
| 3 | Protocol-Aware Assertion Generator | Medium | High | BYTE_ACK sequencing |
| 4 | Dual-Compiler Verification Runner | Small (1-2h) | High | BUG-006 |
| 5 | RTL vs Doc Consistency Checker | Medium (4-8h) | High | BUG-001,002,003,006 |

---

## Prioritized Tool Ideas (Cumulative)

Ranked by impact/effort ratio across all phases:

| Rank | Tool Idea | Effort | Impact | Catches Bugs |
|------|-----------|--------|--------|--------------|
| 1 | Dual-Compiler Verification Runner | Small (1-2h) | High | BUG-006 |
| 2 | RTL vs Doc Consistency Checker | Medium (4-8h) | High | BUG-001,002,003,006 |
| 3 | FSM State Linting | Medium (8-16h) | High | BUG-003 |
| 4 | UVM Project Generator | Medium (8-16h) | High | 50+ compile errors |
| 5 | Register Map Compiler | Medium (4-8h) | High | Register bugs |
| 6 | QuestaSim UVM Launcher | Small (2-4h) | Medium | DPI issues |
| 7 | Doc-vs-RTL Consistency Checker | Medium (4-8h) | Medium | Spec drift |
| 8 | Project Scaffolding Generator | Small (2-4h) | Medium | Setup time |
| 9 | Environment Verification Script | Small (2-4h) | Medium | Missing tools |
| 10 | FSM State Diagram Generator | Small (2-4h) | Medium | Documentation |

### Highest ROI Tools (Build First)

1. **Dual-Compiler Verification Runner** - Smallest effort, catches cross-tool bugs
2. **QuestaSim UVM Launcher** - Automates DPI compilation and test running
3. **RTL vs Doc Consistency Checker** - Would prevent most Phase 2 bugs

---

## Project Summary

### Lines of Code

| Category | Lines | Files |
|----------|-------|-------|
| RTL | 828 | 6 |
| UVM Testbench | ~1,500 | 21 |
| Documentation | ~2,500 | 12 |
| **Total** | **~4,828** | **39** |

### Bugs Found & Fixed

| Phase | Bug Count | Critical |
|-------|-----------|----------|
| Phase 2 RTL | 7 | 3 |
| Phase 3 UVM | 0 | 0 |

### Key Learnings by Phase

**Phase 0**: Project setup is faster with templates
**Phase 1**: Single-source of truth prevents doc inconsistencies
**Phase 2**: Compile success ≠ correct; run multiple tools
**Phase 3**: UVM DPI needs manual compilation for QuestaSim; interface port types matter

### Recommended Workflow for Similar Projects

1. **Before RTL**: Run doc-vs-RTL checker on interface spec
2. **During RTL**: Run dual-compiler (QuestaSim + Yosys) after each module
3. **Before verification**: Compile UVM DPI library first
4. **All phases**: Use systematic review checklists (like this project's debug-methodology)
---

## Phase 4 Retrospective: Visualization Opportunities (Added 2026-03-16)

### Data Generated But Not Visualized

| Data Source | Format | Size | Visualization Opportunity |
|-------------|--------|------|--------------------------|
| Test logs | `sim/*.log` | 5 files | Test dashboard, transaction timeline |
| Synthesis log | `syn/synth.log` | 126KB | Cell distribution pie chart |
| Synthesis JSON | `syn/synth.json` | 418KB | Interactive netlist graph |
| Coverage | `work/*.ucdb` | Binary | FSM coverage heatmap |
| Bug log | `BUG_LOG.md` | 24 bugs | Bug timeline by phase |

### Tools We Should Build for Next Project

1. **Project Dashboard** (16-24 hours)
   - Test status cards (pass/fail with metrics)
   - Coverage gauge
   - Synthesis summary (gate count pie chart)
   - Bug timeline
   - Tech: Python + Chart.js

2. **Test Visualizer** (2-4 hours)
   - Bar chart: transactions per test
   - Highlight mismatches

3. **Synthesis Report Generator** (2-4 hours)
   - Cell type distribution
   - Hierarchy tree

4. **Coverage Heatmap** (8-16 hours)
   - FSM state coverage
   - Uncovered assertions

### Key Lesson
**Build visualization infrastructure BEFORE generating data.** Standardize on JSON log formats and create `make report` target that generates PDF dashboard automatically.

