"""
Unit tests for rtl_analyzer Phase 1 checks.

Standard: Every check must:
  1. Fire on its dedicated buggy fixture (no false negatives).
  2. NOT fire on clean fixtures (no false positives for ERROR/WARNING).
  3. Run in < 500 ms per file.

Comparison baseline: we document what Verilator --lint-only and Verible
would produce for the same fixtures so we can track coverage gaps.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from rtl_analyzer import AnalysisEngine
from rtl_analyzer.models import CheckID, Severity

FIXTURES = Path(__file__).parent / "fixtures"
BUGGY = FIXTURES / "buggy"
CLEAN = FIXTURES / "clean"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def analyze(path: Path):
    engine = AnalysisEngine()
    return engine.analyze_file(path)


def check_ids(result) -> set:
    return {f.check_id for f in result.findings}


def severity_ids(result, sev: Severity) -> set:
    return {f.check_id for f in result.findings if f.severity == sev}


# ---------------------------------------------------------------------------
# Performance — must be fast
# ---------------------------------------------------------------------------

class TestPerformance:
    def test_single_file_under_500ms(self):
        t0 = time.perf_counter()
        analyze(BUGGY / "buggy_counter.v")
        elapsed = (time.perf_counter() - t0) * 1000
        assert elapsed < 500, f"Analysis took {elapsed:.1f} ms — too slow"

    def test_single_sv_under_500ms(self):
        t0 = time.perf_counter()
        analyze(BUGGY / "buggy_fsm.sv")
        elapsed = (time.perf_counter() - t0) * 1000
        assert elapsed < 500, f"Analysis took {elapsed:.1f} ms — too slow"


# ---------------------------------------------------------------------------
# RTL_W005 — sim/synth mismatch (initial block)
# ---------------------------------------------------------------------------

class TestSimSynthMismatch:
    def test_detects_initial_block(self):
        r = analyze(BUGGY / "buggy_counter.v")
        ids = check_ids(r)
        assert CheckID.RTL_W005 in ids, (
            "Should flag 'initial' block as sim/synth mismatch risk. "
            "Verilator INITIALDLY / SpyGlass W29 both flag this."
        )

    def test_clean_counter_no_initial(self):
        r = analyze(CLEAN / "clean_counter.v")
        ids = severity_ids(r, Severity.WARNING) | severity_ids(r, Severity.ERROR)
        # RTL_W005 must NOT appear on clean code
        assert CheckID.RTL_W005 not in ids


# ---------------------------------------------------------------------------
# RTL_E004 — blocking assignment in sequential block
# ---------------------------------------------------------------------------

class TestBlockingInFF:
    def test_detects_blocking_in_ff(self):
        r = analyze(BUGGY / "buggy_counter.v")
        ids = check_ids(r)
        assert CheckID.RTL_E004 in ids, (
            "Should detect blocking '=' inside always @(posedge clk). "
            "Verilator BLKSEQ / SpyGlass W415a both flag this."
        )

    def test_clean_counter_no_blocking_in_ff(self):
        r = analyze(CLEAN / "clean_counter.v")
        assert CheckID.RTL_E004 not in check_ids(r)

    def test_detects_blocking_in_always_ff_sv(self):
        r = analyze(BUGGY / "buggy_fsm.sv")
        assert CheckID.RTL_E004 in check_ids(r)


# ---------------------------------------------------------------------------
# RTL_E005 — non-blocking in combinational block
# ---------------------------------------------------------------------------

class TestNonBlockingInComb:
    def test_detects_nb_in_comb(self):
        r = analyze(BUGGY / "buggy_fsm.sv")
        assert CheckID.RTL_E005 in check_ids(r), (
            "Should detect '<=' inside always_comb. "
            "Verilator BLKANDNBLK / SpyGlass W416a both flag this."
        )

    def test_clean_fsm_no_nb_in_comb(self):
        r = analyze(CLEAN / "clean_fsm.v")
        assert CheckID.RTL_E005 not in check_ids(r)


# ---------------------------------------------------------------------------
# RTL_E001 — latch inference
# ---------------------------------------------------------------------------

class TestLatchInference:
    def test_detects_if_without_else(self):
        r = analyze(BUGGY / "buggy_counter.v")
        assert CheckID.RTL_E001 in check_ids(r), (
            "Should detect if without else in always_comb (latch). "
            "Verilator LATCH / SpyGlass W415 both flag this."
        )

    def test_clean_counter_no_latch(self):
        r = analyze(CLEAN / "clean_counter.v")
        assert CheckID.RTL_E001 not in check_ids(r)

    def test_clean_fsm_no_latch(self):
        r = analyze(CLEAN / "clean_fsm.v")
        # clean_fsm has always_comb with case + default — no latch
        assert CheckID.RTL_E001 not in check_ids(r)


# ---------------------------------------------------------------------------
# RTL_W001 — missing default in case
# ---------------------------------------------------------------------------

class TestMissingDefault:
    def test_detects_case_without_default(self):
        r = analyze(BUGGY / "buggy_counter.v")
        assert CheckID.RTL_W001 in check_ids(r), (
            "Should detect case statement without default. "
            "Verilator CASEINCOMPLETE / Verible case-missing-default flag this."
        )

    def test_clean_fsm_has_default(self):
        r = analyze(CLEAN / "clean_fsm.v")
        assert CheckID.RTL_W001 not in check_ids(r)


# ---------------------------------------------------------------------------
# RTL_W002 — width mismatch
# ---------------------------------------------------------------------------

class TestWidthMismatch:
    def test_detects_truncation(self):
        r = analyze(BUGGY / "buggy_fsm.sv")
        assert CheckID.RTL_W002 in check_ids(r), (
            "Should detect 8-bit literal assigned to 4-bit signal. "
            "Verilator WIDTHTRUNC / SpyGlass W11 both flag this."
        )

    def test_clean_counter_no_width_mismatch(self):
        r = analyze(CLEAN / "clean_counter.v")
        assert CheckID.RTL_W002 not in check_ids(r)


# ---------------------------------------------------------------------------
# RTL_W004 — missing reset on FSM/state register
# ---------------------------------------------------------------------------

class TestMissingReset:
    def test_detects_fsm_without_reset(self):
        r = analyze(BUGGY / "buggy_fsm.sv")
        assert CheckID.RTL_W004 in check_ids(r), (
            "Should detect clocked FSM block without reset. "
            "SpyGlass W17 flags this."
        )

    def test_clean_counter_has_reset_no_warning(self):
        r = analyze(CLEAN / "clean_counter.v")
        assert CheckID.RTL_W004 not in check_ids(r)

    def test_clean_fsm_has_reset_no_warning(self):
        r = analyze(CLEAN / "clean_fsm.v")
        assert CheckID.RTL_W004 not in check_ids(r)


# ---------------------------------------------------------------------------
# Clean files: no ERROR or WARNING should appear
# ---------------------------------------------------------------------------

class TestCleanFilesProduceNoErrorsOrWarnings:
    @pytest.mark.parametrize("fname", [
        "clean_counter.v",
        "clean_fsm.v",
    ])
    def test_clean_file(self, fname: str):
        r = analyze(CLEAN / fname)
        bad = [f for f in r.findings if f.severity in (Severity.ERROR, Severity.WARNING)]
        assert not bad, (
            f"Clean file {fname} produced ERROR/WARNING findings:\n"
            + "\n".join(str(f) for f in bad)
        )


# ---------------------------------------------------------------------------
# Engine API
# ---------------------------------------------------------------------------

class TestEngineAPI:
    def test_analyze_files_returns_result(self):
        engine = AnalysisEngine()
        result = engine.analyze_files([
            BUGGY / "buggy_counter.v",
            CLEAN / "clean_counter.v",
        ])
        assert len(result.file_results) == 2
        assert result.error_count > 0

    def test_suppress_check(self):
        engine = AnalysisEngine(suppress={CheckID.RTL_W005})
        r = engine.analyze_file(BUGGY / "buggy_counter.v")
        assert CheckID.RTL_W005 not in check_ids(r)

    def test_json_output_valid(self):
        import json
        engine = AnalysisEngine()
        result = engine.analyze_files([BUGGY / "buggy_counter.v"])
        data = json.loads(result.to_json())
        assert "findings" in data
        assert "summary" in data
        assert data["summary"]["errors"] > 0

    def test_directory_scan(self, tmp_path):
        import shutil
        shutil.copy(BUGGY / "buggy_counter.v", tmp_path / "test.v")
        engine = AnalysisEngine()
        result = engine.analyze_directory(tmp_path)
        assert len(result.file_results) == 1
        assert result.error_count > 0


# ---------------------------------------------------------------------------
# RTL_W003 — incomplete sensitivity list
# ---------------------------------------------------------------------------

class TestSensitivityList:
    def test_detects_missing_signals(self):
        r = analyze(BUGGY / "buggy_sensitivity.v")
        assert CheckID.RTL_W003 in check_ids(r), (
            "Should detect 'b' and 'sel' missing from always @(a). "
            "SpyGlass W28 flags incomplete sensitivity lists."
        )

    def test_always_star_not_flagged(self):
        # always @(*) has a complete sensitivity list by definition
        r = analyze(CLEAN / "clean_counter.v")
        assert CheckID.RTL_W003 not in check_ids(r)

    def test_always_comb_not_flagged(self):
        # always_comb is always complete
        r = analyze(CLEAN / "clean_fsm.v")
        assert CheckID.RTL_W003 not in check_ids(r)


# ---------------------------------------------------------------------------
# RTL_E003 — multiple drivers
# ---------------------------------------------------------------------------

class TestMultiDriver:
    def test_detects_assign_and_always_both_drive_same_signal(self):
        r = analyze(BUGGY / "buggy_multi_driver.v")
        assert CheckID.RTL_E003 in check_ids(r), (
            "Should detect 'data_out' driven by both assign and always block. "
            "Verilator MULTIDRIVEN / SpyGlass W14 both flag this."
        )

    def test_clean_counter_no_multi_driver(self):
        r = analyze(CLEAN / "clean_counter.v")
        assert CheckID.RTL_E003 not in check_ids(r)

    def test_clean_fsm_no_multi_driver(self):
        r = analyze(CLEAN / "clean_fsm.v")
        assert CheckID.RTL_E003 not in check_ids(r)


# ---------------------------------------------------------------------------
# RTL_I001 / RTL_I002 — unused and undriven signals
# ---------------------------------------------------------------------------

class TestUnusedSignals:
    def test_detects_unused_declared_signal(self):
        r = analyze(BUGGY / "buggy_unused.v")
        assert CheckID.RTL_I001 in check_ids(r), (
            "Should detect 'debug_val' declared but never read. "
            "Verilator UNUSED / SpyGlass W240 both flag this."
        )

    def test_detects_undriven_output(self):
        r = analyze(BUGGY / "buggy_unused.v")
        assert CheckID.RTL_I002 in check_ids(r), (
            "Should detect 'result' used/declared as output but never driven. "
            "Verilator UNDRIVEN / SpyGlass W01 both flag this."
        )

    def test_clean_counter_no_unused(self):
        r = analyze(CLEAN / "clean_counter.v")
        # No RTL_I001 on signals that are actually used
        unused = [f for f in r.findings if f.check_id == CheckID.RTL_I001
                  and f.severity == Severity.INFO]
        assert not unused, f"Unexpected unused-signal findings on clean file: {unused}"


# ---------------------------------------------------------------------------
# RTL_E001 — latch false-positive regression (Bug G)
# ---------------------------------------------------------------------------

class TestLatchNoFalsePositiveOnDefault:
    """
    Regression: a signal with an unconditional default assignment before the
    first 'if' must NOT be flagged as a latch, even when the if has no else.

    Pattern:  always_comb begin x = 0; if (a) x = 1; end
    """

    def test_no_latch_when_default_at_top(self):
        r = analyze(CLEAN / "clean_latch_default_at_top.v")
        latch_findings = [f for f in r.findings if f.check_id == CheckID.RTL_E001]
        assert not latch_findings, (
            "False positive: RTL_E001 fired on a block that has a default "
            "assignment before the if:\n"
            + "\n".join(str(f) for f in latch_findings)
        )

    def test_no_errors_or_warnings_on_clean_default_fixture(self):
        r = analyze(CLEAN / "clean_latch_default_at_top.v")
        bad = [f for f in r.findings if f.severity in (Severity.ERROR, Severity.WARNING)]
        assert not bad, (
            "clean_latch_default_at_top.v produced ERROR/WARNING findings:\n"
            + "\n".join(str(f) for f in bad)
        )


# ---------------------------------------------------------------------------
# RTL_W001 — missing default multi-case regression (Bug H)
# ---------------------------------------------------------------------------

class TestMissingDefaultMultiCase:
    """
    Regression: when two case statements appear in a single always block,
    the depth counter must not confuse 'endcase' with 'case' and must
    correctly identify only the first one (missing default) as buggy.
    """

    def test_fires_on_first_case_missing_default(self):
        r = analyze(BUGGY / "buggy_multi_case.v")
        assert CheckID.RTL_W001 in check_ids(r), (
            "Should detect first case statement (no default) in buggy_multi_case.v. "
            "Bug H regression: depth counter was broken by 'endcase' matching 'case'."
        )

    def test_exactly_one_w001_finding(self):
        """Second case has a default — must produce exactly 1 RTL_W001, not 2."""
        r = analyze(BUGGY / "buggy_multi_case.v")
        w001s = [f for f in r.findings if f.check_id == CheckID.RTL_W001]
        assert len(w001s) == 1, (
            f"Expected exactly 1 RTL_W001 finding, got {len(w001s)}:\n"
            + "\n".join(str(f) for f in w001s)
        )


# ---------------------------------------------------------------------------
# Parse error surfacing (Bug B)
# ---------------------------------------------------------------------------

class TestParseErrorSurfacing:
    """
    Regression: pyslang parse errors must be surfaced as Warning findings,
    not silently dropped.
    """

    def test_parse_error_produces_warning_finding(self):
        r = analyze(BUGGY / "buggy_parse_error.v")
        parse_warnings = [
            f for f in r.findings
            if f.severity == Severity.WARNING and f.source == "pyslang"
        ]
        assert parse_warnings, (
            "buggy_parse_error.v has a syntax error (missing endmodule) but "
            "no WARNING finding from pyslang was produced. Bug B regression."
        )


# ---------------------------------------------------------------------------
# RTL_I003 — empty always block
# ---------------------------------------------------------------------------

class TestEmptyAlways:
    def test_detects_empty_always_block(self):
        r = analyze(BUGGY / "buggy_empty_always.v")
        assert CheckID.RTL_I003 in check_ids(r), (
            "Should flag the empty always @(posedge clk) begin end block. "
            "SpyGlass W16 flags empty blocks."
        )

    def test_non_empty_always_not_flagged(self):
        r = analyze(CLEAN / "clean_counter.v")
        i003s = [f for f in r.findings if f.check_id == CheckID.RTL_I003]
        assert not i003s, (
            f"clean_counter.v should not have empty always blocks, got: {i003s}"
        )

    def test_non_empty_ff_block_not_flagged(self):
        r = analyze(BUGGY / "buggy_empty_always.v")
        # The first (non-empty) FF block must not be flagged
        i003s = [f for f in r.findings if f.check_id == CheckID.RTL_I003]
        # Only the empty block should fire; exactly one finding
        assert len(i003s) == 1, (
            f"Expected exactly 1 RTL_I003 (the empty block), got {len(i003s)}:\n"
            + "\n".join(str(f) for f in i003s)
        )
