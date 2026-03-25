"""Tests for Phase 2 checks (RTL_E006, RTL_W006, RTL_W007)."""

from pathlib import Path

from rtl_analyzer import AnalysisEngine
from rtl_analyzer.models import CheckID, Severity
from rtl_analyzer.parser import parse_file
from rtl_analyzer.elaborator import ElaboratedModule, build_elaborated

FIXTURES = Path(__file__).parent / "fixtures"


def _analyze(path):
    return AnalysisEngine().analyze_file(path)


def test_new_check_ids_exist():
    assert CheckID.RTL_E006.value == "RTL_E006"
    assert CheckID.RTL_W006.value == "RTL_W006"
    assert CheckID.RTL_W007.value == "RTL_W007"


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
    # buggy_cdc.v has no typedef enum FSM — RTL_E006 must not fire on it
    # NOTE: buggy_cdc.v does NOT exist yet — if the file is missing, skip this
    # test for now (it will be created in Task 5). Use clean_counter.v instead.
    r = _analyze(FIXTURES / "clean" / "clean_counter.v")
    e006 = [f for f in r.findings if f.check_id == CheckID.RTL_E006]
    assert not e006, (
        "clean_counter.v has no typedef enum FSM — RTL_E006 must not fire on it"
    )


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
