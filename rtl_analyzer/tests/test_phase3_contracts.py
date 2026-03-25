from click.testing import CliRunner

import rtl_analyzer.cli as cli
from rtl_analyzer.engine import AnalysisEngine, AnalysisResult
from rtl_analyzer.models import CheckID, Finding, Location, Severity


def test_phase3_check_ids_exist():
    assert CheckID.RTL_ML001.value == "RTL_ML001"
    assert CheckID.RTL_ML002.value == "RTL_ML002"
    assert CheckID.RTL_ML003.value == "RTL_ML003"


def test_finding_to_dict_includes_optional_phase3_fields(tmp_path):
    finding = Finding(
        check_id=CheckID.RTL_ML002,
        severity=Severity.WARNING,
        message="AST baseline warning",
        location=Location(file=tmp_path / "demo.v", line=3),
        confidence=0.81,
        metadata={"model": "ast_xgb_v1"},
    )
    payload = finding.to_dict()
    assert payload["confidence"] == 0.81
    assert payload["metadata"]["model"] == "ast_xgb_v1"


def test_engine_phase3_flags_default_to_deterministic_only():
    engine = AnalysisEngine()
    assert getattr(engine, "_phase3_enabled", False) is False
    assert getattr(engine, "_enabled_ml_checks", "missing") is None
    assert getattr(engine, "_model_dir", "missing") is None


def test_engine_normalizes_enabled_ml_checks_to_stable_representation():
    engine = AnalysisEngine(enabled_ml_checks={" AST_XGB_V1 ", "Baseline"})
    assert engine._enabled_ml_checks == frozenset({"ast_xgb_v1", "baseline"})


def test_cli_accepts_hidden_phase3_flags_and_wires_normalized_values(tmp_path, monkeypatch):
    source = tmp_path / "demo.v"
    source.write_text("module demo; endmodule\n")

    captured = {}

    def fake_analyze_files(self, paths):
        captured["phase3_enabled"] = self._phase3_enabled
        captured["enabled_ml_checks"] = self._enabled_ml_checks
        captured["model_dir"] = self._model_dir
        captured["paths"] = paths
        return AnalysisResult()

    monkeypatch.setattr(cli.AnalysisEngine, "analyze_files", fake_analyze_files)

    result = CliRunner().invoke(
        cli.main,
        [
            str(source),
            "--format",
            "json",
            "--exit-zero",
            "--phase3-enabled",
            "--enabled-ml-checks",
            " AST_XGB_V1 , Baseline ",
            "--model-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    assert captured["phase3_enabled"] is True
    assert captured["enabled_ml_checks"] == frozenset({"ast_xgb_v1", "baseline"})
    assert captured["model_dir"] == tmp_path
    assert captured["paths"] == [source]
