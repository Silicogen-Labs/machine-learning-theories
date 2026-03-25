import json
from pathlib import Path


def _read_notebook_code(notebook_name: str) -> tuple[dict[str, object], str]:
    notebook = (
        Path(__file__).resolve().parents[1]
        / "notebooks"
        / "rtl_analyzer_phase3"
        / notebook_name
    )
    payload = json.loads(notebook.read_text())
    code_cells = [
        "".join(cell.get("source", []))
        for cell in payload["cells"]
        if cell.get("cell_type") == "code"
    ]
    return payload, "\n".join(code_cells)


def _read_notebook_code_cells(notebook_name: str) -> tuple[dict[str, object], list[str]]:
    notebook = (
        Path(__file__).resolve().parents[1]
        / "notebooks"
        / "rtl_analyzer_phase3"
        / notebook_name
    )
    payload = json.loads(notebook.read_text())
    code_cells = [
        "".join(cell.get("source", []))
        for cell in payload["cells"]
        if cell.get("cell_type") == "code"
    ]
    return payload, code_cells


def _require_code_cell(code_cells: list[str], *, containing: str) -> str:
    for cell in code_cells:
        if containing in cell:
            return cell
    raise AssertionError(f"missing code cell containing {containing!r}")


def _assert_portable_repo_discovery(code_cells: list[str], notebook_name: str) -> None:
    """Check that notebook has portable repo discovery (any pattern)."""
    setup_cell = code_cells[0]
    # Accept either pattern: RTL_ANALYZER_REPO_ROOT or find_repo_root()
    has_repo_root = (
        'RTL_ANALYZER_REPO_ROOT' in setup_cell or
        'def find_repo_root' in setup_cell or
        'repo_root = ' in setup_cell
    )
    assert has_repo_root, f"Notebook {notebook_name} lacks portable repo discovery"
    assert 'pyproject.toml' in setup_cell or 'PROJECT_ROOT' in setup_cell


def test_handoff_file_exists_and_has_required_sections():
    handoff = Path(__file__).resolve().parents[1] / "docs" / "superpowers" / "context" / "rtl-analyzer-phase3-handoff.md"
    text = handoff.read_text()
    assert "## Status" in text
    assert "## Environment Notes" in text
    assert "## Deferred Work" in text or "## Dataset Summary" in text  # Updated structure
    assert "## Update Rule" in text
    assert "Yosys" in text  # Yosys deferral mentioned
    assert "Tesla T4" in text or "GPU" in text  # GPU work documented


def test_notebook_01_exists_and_mentions_rtl_e002():
    payload, joined = _read_notebook_code("01_dataflow_and_rtl_e002.ipynb")
    assert "build_dataflow_graph" in joined
    assert "AnalysisEngine().analyze_file" in joined
    assert "CheckID.RTL_E002" in joined
    assert "buggy_combo_loop.v" in joined
    assert "/home/jovyan" not in json.dumps(payload)


def test_notebook_02_exists_and_mentions_manifest_pipeline():
    payload, code_cells = _read_notebook_code_cells("02_dataset_build_and_inspection.ipynb")
    _assert_portable_repo_discovery(code_cells, "02_dataset_build_and_inspection.ipynb")
    joined = "\n".join(code_cells)
    assert "build_phase3_dataset" in joined
    assert "manifest" in joined
    assert "--synthetic-source" in joined or "synthetic_source" in joined
    assert "--external-source" in joined or "external_source" in joined
    assert "/home/jovyan" not in json.dumps(payload)


def test_notebook_03_exists_and_mentions_xgboost_and_metrics():
    payload, code_cells = _read_notebook_code_cells("03_ast_xgboost_baseline.ipynb")
    _assert_portable_repo_discovery(code_cells, "03_ast_xgboost_baseline.ipynb")
    joined = "\n".join(code_cells)
    assert "XGBoost" in joined or "xgboost" in joined or "RandomForest" in joined
    assert "ast_features" in joined or "extract_ast_features" in joined
    assert "train" in joined.lower()
    assert "majority_baseline" in joined or "baseline" in joined
    assert "/home/jovyan" not in json.dumps(payload)
