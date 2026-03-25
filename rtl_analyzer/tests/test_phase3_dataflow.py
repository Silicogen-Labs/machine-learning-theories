from pathlib import Path

from rtl_analyzer.dataflow import build_dataflow_graph, find_cycles
from rtl_analyzer.engine import AnalysisEngine
from rtl_analyzer.models import CheckID
from rtl_analyzer.parser import parse_file

FIXTURES = Path(__file__).parent / "fixtures"


def test_build_dataflow_graph_tracks_signal_edges():
    parsed = parse_file(FIXTURES / "buggy" / "buggy_combo_loop.v")
    graph = build_dataflow_graph(parsed)
    assert graph.dependencies["a"] == {"b"}
    assert graph.dependencies["b"] == {"a"}


def test_find_cycles_returns_the_real_feedback_cycle():
    parsed = parse_file(FIXTURES / "buggy" / "buggy_combo_loop.v")
    graph = build_dataflow_graph(parsed)
    assert any(set(cycle) == {"a", "b"} for cycle in find_cycles(graph))


def test_engine_reports_rtl_e002_on_real_cycle():
    result = AnalysisEngine().analyze_file(FIXTURES / "buggy" / "buggy_combo_loop.v")
    assert CheckID.RTL_E002 in {finding.check_id for finding in result.findings}


def test_registered_feedback_is_not_reported_as_comb_loop():
    result = AnalysisEngine().analyze_file(FIXTURES / "clean" / "clean_registered_feedback.v")
    assert CheckID.RTL_E002 not in {finding.check_id for finding in result.findings}


def test_branch_split_assignments_do_not_create_false_cycle():
    result = AnalysisEngine().analyze_file(FIXTURES / "clean" / "clean_branch_split_feedback.v")
    assert CheckID.RTL_E002 not in {finding.check_id for finding in result.findings}


def test_same_signal_names_in_separate_modules_do_not_alias_into_cycle():
    result = AnalysisEngine().analyze_file(FIXTURES / "clean" / "clean_multi_module_alias.v")
    assert CheckID.RTL_E002 not in {finding.check_id for finding in result.findings}


def test_sized_literals_do_not_create_fake_identifier_dependencies():
    parsed = parse_file(FIXTURES / "clean" / "clean_literal_assign.v")
    graph = build_dataflow_graph(parsed)
    assert graph.dependencies["a"] == set()
