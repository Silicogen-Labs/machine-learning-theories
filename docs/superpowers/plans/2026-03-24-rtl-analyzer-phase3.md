# RTL Analyzer Phase 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver Phase 3 in a practical server-safe order: real `RTL_E002`, reproducible datasets, notebook deliverables, an AST + XGBoost baseline as the first real model, and a later LLM security-scanner path, while keeping the default deterministic CLI path unchanged.

**Architecture:** Keep two lanes with a strict priority order. The deterministic lane adds a shared dataflow DAG and a real `RTL_E002`; the ML lane stays fully feature-gated, starts with manifest-driven reproducible datasets, and treats AST + XGBoost as the main ML success criterion on this server. Real Yosys-backed graph extraction and GNN training are explicitly deferred to the other server where Yosys is installed; this server only gets an optional non-blocking scaffold.

**Tech Stack:** Python 3.12, `pyslang`, `click`, `rich`, `pytest`, optional `xgboost`/`scikit-learn`/`joblib`, notebook tooling (`nbformat`, `nbclient`, `jupyter`), and optional LLM tooling (`transformers`, `datasets`, `peft`, `accelerate`, `bitsandbytes`) for a Qwen3.5 + Unsloth-style LoRA/QLoRA workflow.

---

## File Structure

- `rtl_analyzer/rtl_analyzer/models.py` - Phase 3 IDs, finding metadata, and feature-flag contracts.
- `rtl_analyzer/rtl_analyzer/engine.py` - deterministic default path plus optional ML configuration plumbing.
- `rtl_analyzer/rtl_analyzer/cli.py` - explicit feature flags and model-path options; deterministic default stays untouched.
- `rtl_analyzer/rtl_analyzer/dataflow.py` - shared dataflow DAG builder and cycle analysis used by `RTL_E002` and later AST features.
- `rtl_analyzer/rtl_analyzer/checks/combinational_loop.py` - real `RTL_E002` implementation backed by the shared DAG.
- `rtl_analyzer/rtl_analyzer/ml/dataset_manifest.py` - manifest schema, provenance, stable splits, and reproducibility helpers.
- `rtl_analyzer/rtl_analyzer/ml/ast_features.py` - first real feature extractor for this server.
- `rtl_analyzer/rtl_analyzer/ml/classifiers.py` - XGBoost baseline wrapper first; optional graph stub later.
- `rtl_analyzer/rtl_analyzer/ml/vulnerability_scanner.py` - prompt packing, inference schema, and fine-tuning dataset helpers for the security scanner.
- `rtl_analyzer/rtl_analyzer/ml/circuit_graph.py` - optional graph contract only; real Yosys-backed training stays deferred to the other server.
- `rtl_analyzer/scripts/build_phase3_dataset.py` - reproducible dataset build entry point.
- `rtl_analyzer/scripts/train_ast_baseline.py` - AST baseline training entry point.
- `rtl_analyzer/scripts/evaluate_phase3.py` - reproducible evaluation and report generation.
- `rtl_analyzer/scripts/fine_tune_llm_scanner.py` - Qwen3.5 security-scanner dry run and optional fine-tuning recipe.
- `rtl_analyzer/tests/test_phase3_contracts.py` - feature-flag and metadata contract tests.
- `rtl_analyzer/tests/test_phase3_dataflow.py` - shared DAG and `RTL_E002` regression tests.
- `rtl_analyzer/tests/test_phase3_dataset.py` - manifest, split, and dataset build tests.
- `rtl_analyzer/tests/test_phase3_ml.py` - AST feature extraction, XGBoost baseline, and optional graph scaffold tests.
- `rtl_analyzer/tests/test_phase3_docs.py` - handoff-file and notebook contract tests.
- `rtl_analyzer/tests/test_phase3_llm.py` - prompt-path and fine-tuning workflow tests.
- `rtl_analyzer/tests/test_phase3_integration.py` - engine/CLI integration tests.
- `docs/superpowers/context/rtl-analyzer-phase3-handoff.md` - persistent handoff file; update it as each task completes.
- `notebooks/rtl_analyzer_phase3/01_dataflow_and_rtl_e002.ipynb` - notebook deliverable for DAG and real `RTL_E002`.
- `notebooks/rtl_analyzer_phase3/02_dataset_build_and_inspection.ipynb` - notebook deliverable for dataset build and manifest inspection.
- `notebooks/rtl_analyzer_phase3/03_ast_xgboost_baseline.ipynb` - notebook deliverable for AST baseline training and evaluation.
- `notebooks/rtl_analyzer_phase3/04_llm_security_scanner.ipynb` - notebook deliverable for prompt flow, dataset shaping, and Qwen3.5 fine-tuning workflow.

## Scope Guardrails

- Keep ML checks behind explicit feature flags; a normal `rtl-check path/to/file.v` run must remain deterministic and usable without optional ML dependencies.
- Treat AST + XGBoost as the first real model and the main ML success criterion on this server.
- Do not include `RTL_E006` or `RTL_W007` enhancements in this plan.
- Treat graph/GNN work as optional and non-blocking here.
- State clearly in docs, tests, and CLI help that real Yosys-backed GNN training is deferred to the other server.

## Server Reality

- Expected current-server behavior: `yosys` is unavailable, so all required verification commands in this plan must still pass without it.
- Optional graph/GNN commands must produce a clear skip or deferred message instead of blocking the rest of Phase 3.
- LLM fine-tuning is a recipe deliverable on this server; actual adapter training is only required on suitable hardware.

---

### Task 1: Add Phase 3 contracts and feature flags first

**Files:**
- Modify: `rtl_analyzer/rtl_analyzer/models.py`
- Modify: `rtl_analyzer/rtl_analyzer/engine.py`
- Modify: `rtl_analyzer/rtl_analyzer/cli.py`
- Modify: `rtl_analyzer/pyproject.toml`
- Test: `rtl_analyzer/tests/test_phase3_contracts.py`

- [ ] **Step 1: Write the failing contract tests**

```python
from rtl_analyzer.models import CheckID, Finding, Location, Severity
from rtl_analyzer.engine import AnalysisEngine


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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /home/jovyan/silicogen/rtl_analyzer && python -m pytest tests/test_phase3_contracts.py -v`
Expected: FAIL because the new IDs, optional finding fields, and Phase 3 flag contract do not exist yet.

- [ ] **Step 3: Add the minimal contracts in code**

```python
class CheckID(str, enum.Enum):
    RTL_ML001 = "RTL_ML001"
    RTL_ML002 = "RTL_ML002"
    RTL_ML003 = "RTL_ML003"


@dataclasses.dataclass(frozen=True)
class Finding:
    confidence: Optional[float] = None
    metadata: dict = dataclasses.field(default_factory=dict)
```

- [ ] **Step 4: Add explicit but inactive feature-flag plumbing**

```python
class AnalysisEngine:
    def __init__(..., phase3_enabled: bool = False, enabled_ml_checks: Optional[set[str]] = None, model_dir: Optional[Path] = None):
        self._phase3_enabled = phase3_enabled
        self._enabled_ml_checks = enabled_ml_checks or set()
        self._model_dir = model_dir
```

Run: `cd /home/jovyan/silicogen/rtl_analyzer && python -m pytest tests/test_phase3_contracts.py -v`
Expected: PASS.

- [ ] **Step 5: Add optional dependencies without changing the default install path**

```toml
[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-cov>=5.0"]
ml = ["numpy>=1.26", "scikit-learn>=1.5", "xgboost>=2.1", "joblib>=1.4"]
notebooks = ["jupyter>=1.1", "nbformat>=5.10", "nbclient>=0.10", "nbconvert>=7.16"]
llm = ["transformers>=4.50", "datasets>=3.2", "peft>=0.14", "accelerate>=1.3", "bitsandbytes>=0.45"]
```

- [ ] **Step 6: Prove the deterministic path is still untouched**

Run: `cd /home/jovyan/silicogen/rtl_analyzer && python -m pytest tests/test_checks.py tests/test_phase2.py -v`
Expected: PASS; existing deterministic checks still run without ML extras.

- [ ] **Step 7: Commit**

```bash
git add rtl_analyzer/rtl_analyzer/models.py rtl_analyzer/rtl_analyzer/engine.py rtl_analyzer/rtl_analyzer/cli.py rtl_analyzer/pyproject.toml rtl_analyzer/tests/test_phase3_contracts.py
git commit -m "feat(phase3): add contracts and feature flags"
```

---

### Task 2: Build the shared dataflow DAG and replace the `RTL_E002` stub

**Files:**
- Create: `rtl_analyzer/rtl_analyzer/dataflow.py`
- Modify: `rtl_analyzer/rtl_analyzer/checks/combinational_loop.py`
- Test: `rtl_analyzer/tests/test_phase3_dataflow.py`
- Create: `rtl_analyzer/tests/fixtures/buggy/buggy_combo_loop.v`
- Create: `rtl_analyzer/tests/fixtures/clean/clean_registered_feedback.v`

- [ ] **Step 1: Write the failing DAG and loop-detection tests**

```python
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
```

- [ ] **Step 2: Add the positive and negative RTL fixtures**

Run: `cd /home/jovyan/silicogen/rtl_analyzer && python -m pytest tests/test_phase3_dataflow.py -v`
Expected: FAIL because `rtl_analyzer/dataflow.py` does not exist and `RTL_E002` is still a stub.

- [ ] **Step 3: Implement the smallest reusable DAG API**

```python
@dataclass
class DataflowGraph:
    dependencies: dict[str, set[str]]
    assignment_lines: dict[str, int]


def build_dataflow_graph(parsed_file) -> DataflowGraph:
    # Build dependencies from comment-stripped combinational assignments only.
    # Ignore always_ff / registered assignments.
    return DataflowGraph(dependencies={}, assignment_lines={})


def find_cycles(graph: DataflowGraph) -> list[list[str]]:
    # Return stable, deduplicated cycles as lists of signal names.
    return []
```

- [ ] **Step 4: Replace the `RTL_E002` stub with real cycle detection**

```python
def check_combinational_loop(pf):
    graph = build_dataflow_graph(pf)
    cycles = find_cycles(graph)
    findings = []
    for cycle in cycles:
        earliest = min(graph.assignment_lines.get(name, 1) for name in cycle)
        findings.append((cycle, earliest))
    return findings
```

- [ ] **Step 5: Re-run the focused tests**

Run: `cd /home/jovyan/silicogen/rtl_analyzer && python -m pytest tests/test_phase3_dataflow.py tests/test_checks.py::TestCleanFilesProduceNoErrorsOrWarnings -v`
Expected: PASS; `buggy_combo_loop.v` fires `RTL_E002` and registered feedback stays clean.

- [ ] **Step 6: Run the full deterministic suite**

Run: `cd /home/jovyan/silicogen/rtl_analyzer && python -m pytest tests/test_checks.py tests/test_phase2.py tests/test_phase3_dataflow.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add rtl_analyzer/rtl_analyzer/dataflow.py rtl_analyzer/rtl_analyzer/checks/combinational_loop.py rtl_analyzer/tests/test_phase3_dataflow.py rtl_analyzer/tests/fixtures/buggy/buggy_combo_loop.v rtl_analyzer/tests/fixtures/clean/clean_registered_feedback.v
git commit -m "feat(phase3): add shared dataflow DAG and real RTL_E002"
```

---

### Task 3: Create the persistent handoff file early and require ongoing updates

**Files:**
- Create: `docs/superpowers/context/rtl-analyzer-phase3-handoff.md`
- Test: `rtl_analyzer/tests/test_phase3_docs.py`

- [ ] **Step 1: Write the failing handoff-file contract test**

```python
from pathlib import Path


def test_handoff_file_exists_and_has_required_sections():
    handoff = Path(__file__).resolve().parents[2] / "docs" / "superpowers" / "context" / "rtl-analyzer-phase3-handoff.md"
    text = handoff.read_text()
    assert "## Status" in text
    assert "## Environment Notes" in text
    assert "## Artifacts" in text
    assert "## Deferred Work" in text
    assert "Yosys-backed GNN training is deferred to the other server." in text
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd /home/jovyan/silicogen/rtl_analyzer && python -m pytest tests/test_phase3_docs.py::test_handoff_file_exists_and_has_required_sections -v`
Expected: FAIL because the handoff file does not exist yet.

- [ ] **Step 3: Create the handoff file with real operational content**

```markdown
# RTL Analyzer Phase 3 Handoff

## Status
- Task 1: complete
- Task 2: complete
- Task 3: in progress

## Environment Notes
- Current server: Yosys unavailable
- Default path must stay deterministic

## Artifacts
- Dataset: pending
- AST model: pending

## Deferred Work
- Yosys-backed GNN training is deferred to the other server.
```

- [ ] **Step 4: Re-run the handoff-file test**

Run: `cd /home/jovyan/silicogen/rtl_analyzer && python -m pytest tests/test_phase3_docs.py::test_handoff_file_exists_and_has_required_sections -v`
Expected: PASS.

- [ ] **Step 5: Add the update rule to the handoff file itself**

```markdown
## Update Rule
- Update this file at the end of every completed Phase 3 task.
- Record artifact paths, environment gaps, deferred items, and the next recommended action.
```

- [ ] **Step 6: Commit**

```bash
git add docs/superpowers/context/rtl-analyzer-phase3-handoff.md rtl_analyzer/tests/test_phase3_docs.py
git commit -m "docs(phase3): add persistent handoff file"
```

---

### Task 4: Build the dataset manifest and reproducible dataset build flow

**Files:**
- Create: `rtl_analyzer/rtl_analyzer/ml/__init__.py`
- Create: `rtl_analyzer/rtl_analyzer/ml/dataset_manifest.py`
- Create: `rtl_analyzer/scripts/build_phase3_dataset.py`
- Test: `rtl_analyzer/tests/test_phase3_dataset.py`
- Modify: `docs/superpowers/context/rtl-analyzer-phase3-handoff.md`

- [ ] **Step 1: Write the failing manifest and reproducibility tests**

```python
from rtl_analyzer.ml.dataset_manifest import DatasetEntry, build_grouped_splits, read_manifest, write_manifest


def test_grouped_split_is_deterministic(tmp_path):
    entries = [
        DatasetEntry(sample_id="a", source_group="repo_a", source_type="synthetic", path="a.v", labels=["clean"]),
        DatasetEntry(sample_id="b", source_group="repo_b", source_type="external", path="b.v", labels=["combo_loop"]),
        DatasetEntry(sample_id="c", source_group="repo_c", source_type="external", path="c.v", labels=["clean"]),
    ]
    assert build_grouped_splits(entries, seed=7) == build_grouped_splits(entries, seed=7)


def test_manifest_round_trip_preserves_seed_and_sha(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    entry = DatasetEntry(sample_id="demo", source_group="repo_x", source_type="external", path="demo.v", labels=["clean"], sha256="abc")
    write_manifest(manifest_path, [entry], seed=7)
    manifest = read_manifest(manifest_path)
    assert manifest.seed == 7
    assert manifest.entries[0].sha256 == "abc"


def test_manifest_can_store_security_scanner_fields(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    entry = DatasetEntry(
        sample_id="sec-1",
        source_group="repo_sec",
        source_type="external",
        path="demo.v",
        labels=["clean"],
        security_labels=["CWE-1245"],
        rationale="demo rationale",
        line_hints=[12, 18],
    )
    write_manifest(manifest_path, [entry], seed=7)
    manifest = read_manifest(manifest_path)
    assert manifest.entries[0].security_labels == ["CWE-1245"]
    assert manifest.entries[0].line_hints == [12, 18]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /home/jovyan/silicogen/rtl_analyzer && python -m pytest tests/test_phase3_dataset.py -v`
Expected: FAIL because the manifest module and build script do not exist yet.

- [ ] **Step 3: Implement the manifest schema and grouped split helpers**

```python
@dataclass(frozen=True)
class DatasetEntry:
    sample_id: str
    source_group: str
    source_type: str
    path: str
    labels: list[str]
    security_labels: list[str] = field(default_factory=list)
    rationale: str = ""
    line_hints: list[int] = field(default_factory=list)
    sha256: str = ""
    split: str = ""
    metadata: dict[str, object] = field(default_factory=dict)
```

Security-data rule:

```python
- `labels` remain the generic bug-class labels for deterministic/AST work
- `security_labels` store CWE-style labels for LLM work
- `rationale` and `line_hints` are optional but must round-trip through the manifest
- `fine_tune_llm_scanner.py` consumes `security_labels`, `rationale`, `line_hints`, and manifest-resolved `path`
```

- [ ] **Step 4: Add the reproducible dataset build script**

Run: `cd /home/jovyan/silicogen/rtl_analyzer && python scripts/build_phase3_dataset.py --output-dir /tmp/rtl_phase3_dataset --seed 7 --synthetic-source tests/fixtures/buggy --external-source tests/fixtures/clean`
Expected: a controlled first-pass manifest write or a clear "source layout not implemented yet" failure message with no traceback.

- [ ] **Step 5: Make the build output real and deterministic**

Expected outputs after implementation:
- `/tmp/rtl_phase3_dataset/manifest.json`
- `/tmp/rtl_phase3_dataset/train/`
- `/tmp/rtl_phase3_dataset/val/`
- `/tmp/rtl_phase3_dataset/test/`

- [ ] **Step 6: Re-run the focused tests and script smoke test**

Run: `cd /home/jovyan/silicogen/rtl_analyzer && python -m pytest tests/test_phase3_dataset.py -v && python scripts/build_phase3_dataset.py --output-dir /tmp/rtl_phase3_dataset --seed 7 --synthetic-source tests/fixtures/buggy --external-source tests/fixtures/clean`
Expected: PASS for tests; script writes `manifest.json` with stable split assignments and provenance.

- [ ] **Step 7: Update the handoff file**

Add:

```markdown
## Status
- Task 4: complete

## Artifacts
- Dataset manifest: /tmp/rtl_phase3_dataset/manifest.json
```

- [ ] **Step 8: Commit**

```bash
git add rtl_analyzer/rtl_analyzer/ml/__init__.py rtl_analyzer/rtl_analyzer/ml/dataset_manifest.py rtl_analyzer/scripts/build_phase3_dataset.py rtl_analyzer/tests/test_phase3_dataset.py docs/superpowers/context/rtl-analyzer-phase3-handoff.md
git commit -m "feat(phase3): add reproducible dataset manifest and build flow"
```

---

### Task 5: Deliver notebook 1 for dataflow and real `RTL_E002`

**Files:**
- Create: `notebooks/rtl_analyzer_phase3/01_dataflow_and_rtl_e002.ipynb`
- Modify: `rtl_analyzer/tests/test_phase3_docs.py`
- Modify: `docs/superpowers/context/rtl-analyzer-phase3-handoff.md`

- [ ] **Step 0: Install notebook tooling**

Run: `cd /home/jovyan/silicogen/rtl_analyzer && python -m pip install -e '.[dev,notebooks]'`
Expected: `jupyter`, `nbformat`, `nbclient`, and `nbconvert` are available for notebook execution.

- [ ] **Step 1: Write the failing notebook contract test**

```python
import json
from pathlib import Path


def test_notebook_01_exists_and_mentions_rtl_e002():
    notebook = Path(__file__).resolve().parents[2] / "notebooks" / "rtl_analyzer_phase3" / "01_dataflow_and_rtl_e002.ipynb"
    payload = json.loads(notebook.read_text())
    joined = json.dumps(payload)
    assert "RTL_E002" in joined
    assert "build_dataflow_graph" in joined
    assert "buggy_combo_loop.v" in joined
```

- [ ] **Step 2: Run the notebook contract test to verify it fails**

Run: `cd /home/jovyan/silicogen/rtl_analyzer && python -m pytest tests/test_phase3_docs.py::test_notebook_01_exists_and_mentions_rtl_e002 -v`
Expected: FAIL because notebook 1 does not exist yet.

- [ ] **Step 3: Author notebook 1 as a real deliverable**

Required notebook sections:
- load `rtl_analyzer/tests/fixtures/buggy/buggy_combo_loop.v`
- call the shared DAG path
- show a real `RTL_E002` result
- explain how to rerun the script and test path

- [ ] **Step 4: Execute notebook 1**

Run: `cd /home/jovyan/silicogen && python -m jupyter nbconvert --to notebook --execute --inplace notebooks/rtl_analyzer_phase3/01_dataflow_and_rtl_e002.ipynb`
Expected: notebook executes in place and stores rendered outputs with no traceback.

- [ ] **Step 5: Re-run the contract test**

Run: `cd /home/jovyan/silicogen/rtl_analyzer && python -m pytest tests/test_phase3_docs.py::test_notebook_01_exists_and_mentions_rtl_e002 -v`
Expected: PASS.

- [ ] **Step 6: Update the handoff file**

Add notebook path and execution status:

```markdown
- Notebook 01: notebooks/rtl_analyzer_phase3/01_dataflow_and_rtl_e002.ipynb
```

- [ ] **Step 7: Commit**

```bash
git add notebooks/rtl_analyzer_phase3/01_dataflow_and_rtl_e002.ipynb rtl_analyzer/tests/test_phase3_docs.py docs/superpowers/context/rtl-analyzer-phase3-handoff.md
git commit -m "docs(phase3): add notebook for dataflow and RTL_E002"
```

---

### Task 6: Implement AST features and the XGBoost baseline as the first real model

**Files:**
- Create: `rtl_analyzer/rtl_analyzer/ml/ast_features.py`
- Create: `rtl_analyzer/rtl_analyzer/ml/classifiers.py`
- Create: `rtl_analyzer/scripts/train_ast_baseline.py`
- Create: `rtl_analyzer/scripts/evaluate_phase3.py`
- Test: `rtl_analyzer/tests/test_phase3_ml.py`
- Modify: `docs/superpowers/context/rtl-analyzer-phase3-handoff.md`

- [ ] **Step 1: Write the failing AST-feature and baseline tests**

```python
from pathlib import Path

from rtl_analyzer.ml.ast_features import extract_ast_features
from rtl_analyzer.parser import parse_file

FIXTURES = Path(__file__).parent / "fixtures"


def test_ast_features_include_dataflow_counts():
    parsed = parse_file(FIXTURES / "clean" / "clean_counter.v")
    features = extract_ast_features(parsed)
    assert "always_block_count" in features
    assert "assign_count" in features
    assert "dataflow_cycle_count" in features
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /home/jovyan/silicogen/rtl_analyzer && python -m pytest tests/test_phase3_ml.py -k ast -v`
Expected: FAIL because the AST feature and classifier modules do not exist yet.

- [ ] **Step 3: Implement the smallest real AST feature extractor**

```python
def extract_ast_features(parsed_file) -> dict[str, float]:
    return {
        "always_block_count": float(len(parsed_file.always_blocks)),
        "assign_count": float(parsed_file.source.count("assign")),
        "dataflow_node_count": 0.0,
        "dataflow_cycle_count": 0.0,
    }
```

- [ ] **Step 4: Add the XGBoost wrapper and training entry point**

Run: `cd /home/jovyan/silicogen/rtl_analyzer && python -m pip install -e '.[dev,ml]'`
Expected: optional ML dependencies install without changing the base install path.

- [ ] **Step 5: Train the baseline on the reproducible manifest**

Run: `cd /home/jovyan/silicogen/rtl_analyzer && python scripts/train_ast_baseline.py --manifest /tmp/rtl_phase3_dataset/manifest.json --model-dir /tmp/rtl_phase3_models --predictions-out /tmp/rtl_phase3_models/ast_predictions.jsonl --metrics-out /tmp/rtl_phase3_models/ast_metrics.json --baseline-out /tmp/rtl_phase3_models/majority_baseline.json`
Expected outputs:
- `/tmp/rtl_phase3_models/ast/model.json`
- `/tmp/rtl_phase3_models/ast/labels.json`
- `/tmp/rtl_phase3_models/ast/thresholds.json`
- `/tmp/rtl_phase3_models/ast_predictions.jsonl`
- `/tmp/rtl_phase3_models/ast_metrics.json`
- `/tmp/rtl_phase3_models/majority_baseline.json`

- [ ] **Step 6: Verify the AST baseline is the first real ML success criterion**

Run: `cd /home/jovyan/silicogen/rtl_analyzer && python scripts/evaluate_phase3.py --manifest /tmp/rtl_phase3_dataset/manifest.json --predictions /tmp/rtl_phase3_models/ast_predictions.jsonl --report-out /tmp/rtl_phase3_models/report.json`
Expected: evaluation report shows the AST baseline beating the majority baseline on the held-out test split before Phase 3 is considered successful on this server.

- [ ] **Step 7: Re-run focused tests**

Run: `cd /home/jovyan/silicogen/rtl_analyzer && python -m pytest tests/test_phase3_ml.py -k ast -v`
Expected: PASS.

- [ ] **Step 8: Update the handoff file**

Record the dataset manifest, AST model directory, and the measured baseline result.

- [ ] **Step 9: Commit**

```bash
git add rtl_analyzer/rtl_analyzer/ml/ast_features.py rtl_analyzer/rtl_analyzer/ml/classifiers.py rtl_analyzer/scripts/train_ast_baseline.py rtl_analyzer/scripts/evaluate_phase3.py rtl_analyzer/tests/test_phase3_ml.py docs/superpowers/context/rtl-analyzer-phase3-handoff.md
git commit -m "feat(phase3): add AST features and XGBoost baseline"
```

---

### Task 7: Deliver notebooks 2 and 3 for dataset reproducibility and AST baseline analysis

**Files:**
- Create: `notebooks/rtl_analyzer_phase3/02_dataset_build_and_inspection.ipynb`
- Create: `notebooks/rtl_analyzer_phase3/03_ast_xgboost_baseline.ipynb`
- Modify: `rtl_analyzer/tests/test_phase3_docs.py`
- Modify: `docs/superpowers/context/rtl-analyzer-phase3-handoff.md`

- [ ] **Step 0: Confirm notebook tooling is installed**

Run: `cd /home/jovyan/silicogen/rtl_analyzer && python -m pip install -e '.[dev,notebooks]'`
Expected: notebook execution dependencies are already present or install cleanly.

- [ ] **Step 1: Write the failing notebook contract tests**

```python
def test_notebook_02_exists_and_mentions_manifest():
    notebook = Path(__file__).resolve().parents[2] / "notebooks" / "rtl_analyzer_phase3" / "02_dataset_build_and_inspection.ipynb"
    payload = json.loads(notebook.read_text())
    joined = json.dumps(payload)
    assert "manifest.json" in joined
    assert "build_phase3_dataset.py" in joined


def test_notebook_03_exists_and_mentions_xgboost_and_metrics():
    notebook = Path(__file__).resolve().parents[2] / "notebooks" / "rtl_analyzer_phase3" / "03_ast_xgboost_baseline.ipynb"
    payload = json.loads(notebook.read_text())
    joined = json.dumps(payload)
    assert "XGBoost" in joined or "xgboost" in joined
    assert "majority_baseline.json" in joined
    assert "ast_predictions.jsonl" in joined
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /home/jovyan/silicogen/rtl_analyzer && python -m pytest tests/test_phase3_docs.py -k 'notebook_02 or notebook_03' -v`
Expected: FAIL because notebooks 2 and 3 do not exist yet.

- [ ] **Step 3: Author notebook 2 as a reproducible dataset deliverable**

Notebook 2 must show:
- how `rtl_analyzer/scripts/build_phase3_dataset.py` is invoked
- how `manifest.json` is inspected
- how split counts and provenance are checked

- [ ] **Step 4: Author notebook 3 as a reproducible AST-baseline deliverable**

Notebook 3 must show:
- loading the manifest
- extracting AST features
- training the XGBoost baseline
- comparing against `majority_baseline.json`
- pointing to `/tmp/rtl_phase3_models/report.json`

- [ ] **Step 5: Execute both notebooks**

Run: `cd /home/jovyan/silicogen && python -m jupyter nbconvert --to notebook --execute --inplace notebooks/rtl_analyzer_phase3/02_dataset_build_and_inspection.ipynb && python -m jupyter nbconvert --to notebook --execute --inplace notebooks/rtl_analyzer_phase3/03_ast_xgboost_baseline.ipynb`
Expected: both notebooks execute in place with no traceback.

- [ ] **Step 6: Re-run the notebook tests**

Run: `cd /home/jovyan/silicogen/rtl_analyzer && python -m pytest tests/test_phase3_docs.py -k 'notebook_02 or notebook_03' -v`
Expected: PASS.

- [ ] **Step 7: Update the handoff file**

Add notebooks 2 and 3 plus their latest execution date and artifact paths.

- [ ] **Step 8: Commit**

```bash
git add notebooks/rtl_analyzer_phase3/02_dataset_build_and_inspection.ipynb notebooks/rtl_analyzer_phase3/03_ast_xgboost_baseline.ipynb rtl_analyzer/tests/test_phase3_docs.py docs/superpowers/context/rtl-analyzer-phase3-handoff.md
git commit -m "docs(phase3): add dataset and AST baseline notebooks"
```

---

### Task 8: Add the LLM security-scanner prompt path and fine-tuning workflow

**Files:**
- Create: `rtl_analyzer/rtl_analyzer/ml/vulnerability_scanner.py`
- Create: `rtl_analyzer/scripts/fine_tune_llm_scanner.py`
- Test: `rtl_analyzer/tests/test_phase3_llm.py`
- Modify: `docs/superpowers/context/rtl-analyzer-phase3-handoff.md`

- [ ] **Step 1: Write the failing prompt and workflow tests**

```python
from rtl_analyzer.ml.vulnerability_scanner import build_prompt, manifest_to_instruction_rows


def test_build_prompt_mentions_json_schema_and_filename():
    prompt = build_prompt("module demo; endmodule", file_name="demo.v")
    assert "demo.v" in prompt
    assert "JSON" in prompt
    assert "CWE" in prompt


def test_manifest_rows_skip_missing_security_labels():
    rows = manifest_to_instruction_rows([
        {"sample_id": "a", "path": "demo.v", "code": "module demo; endmodule", "security_labels": [], "source_type": "external"}
    ])
    assert rows == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /home/jovyan/silicogen/rtl_analyzer && python -m pytest tests/test_phase3_llm.py -v`
Expected: FAIL because the vulnerability-scanner module does not exist yet.

- [ ] **Step 3: Implement the prompt path for security scanning, not generic linting**

```python
def build_prompt(source_text: str, file_name: str) -> str:
    return (
        f"Analyze {file_name} for hardware security vulnerabilities. "
        "Return JSON with keys: cwe_id, confidence, rationale, line_hints.\n\n"
        f"RTL:\n{source_text}"
    )


def manifest_to_instruction_rows(rows: list[dict]) -> list[dict]:
    return [
        {
            "input": row["code"],
            "output": row["security_labels"],
            "sample_id": row["sample_id"],
        }
        for row in rows
        if row.get("security_labels")
    ]
```

- [ ] **Step 4: Implement the Qwen3.5 fine-tuning workflow definition**

Required defaults:
- base model: `Qwen/Qwen3.5` family recommendation in docs and script help
- fine-tuning style: Unsloth-style LoRA or QLoRA
- dry-run path writes train/eval JSONL plus config without launching training

- [ ] **Step 5: Dry-run the workflow on this server**

Run: `cd /home/jovyan/silicogen/rtl_analyzer && python scripts/fine_tune_llm_scanner.py --manifest /tmp/rtl_phase3_dataset/manifest.json --output-dir /tmp/rtl_phase3_llm --base-model Qwen/Qwen3.5 --dry-run`
Expected outputs:
- `/tmp/rtl_phase3_llm/train.jsonl`
- `/tmp/rtl_phase3_llm/eval.jsonl`
- `/tmp/rtl_phase3_llm/lora_config.json`
- summary showing skipped rows without `security_labels`

- [ ] **Step 6: Keep actual training optional and hardware-gated**

Run: `cd /home/jovyan/silicogen/rtl_analyzer && python scripts/fine_tune_llm_scanner.py --manifest /tmp/rtl_phase3_dataset/manifest.json --output-dir /tmp/rtl_phase3_llm --base-model Qwen/Qwen3.5 --run-train --max-steps 200`
Expected: on this server, a clear dependency or hardware gate message is acceptable; on a suitable GPU server, LoRA/QLoRA training should start without redesign.

- [ ] **Step 7: Re-run the focused tests**

Run: `cd /home/jovyan/silicogen/rtl_analyzer && python -m pytest tests/test_phase3_llm.py -v`
Expected: PASS.

- [ ] **Step 8: Update the handoff file**

Record the Qwen3.5 recommendation, dry-run artifact paths, and any skipped-label counts.

- [ ] **Step 9: Commit**

```bash
git add rtl_analyzer/rtl_analyzer/ml/vulnerability_scanner.py rtl_analyzer/scripts/fine_tune_llm_scanner.py rtl_analyzer/tests/test_phase3_llm.py docs/superpowers/context/rtl-analyzer-phase3-handoff.md
git commit -m "feat(phase3): add LLM security scanner workflow"
```

---

### Task 9: Deliver notebook 4 for the LLM security-scanner workflow

**Files:**
- Create: `notebooks/rtl_analyzer_phase3/04_llm_security_scanner.ipynb`
- Modify: `rtl_analyzer/tests/test_phase3_docs.py`
- Modify: `docs/superpowers/context/rtl-analyzer-phase3-handoff.md`

- [ ] **Step 1: Write the failing notebook contract test**

```python
def test_notebook_04_exists_and_mentions_qwen_and_lora():
    notebook = Path(__file__).resolve().parents[2] / "notebooks" / "rtl_analyzer_phase3" / "04_llm_security_scanner.ipynb"
    payload = json.loads(notebook.read_text())
    joined = json.dumps(payload)
    assert "Qwen3.5" in joined or "Qwen/Qwen3.5" in joined
    assert "LoRA" in joined or "QLoRA" in joined
    assert "security_labels" in joined
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd /home/jovyan/silicogen/rtl_analyzer && python -m pytest tests/test_phase3_docs.py::test_notebook_04_exists_and_mentions_qwen_and_lora -v`
Expected: FAIL because notebook 4 does not exist yet.

- [ ] **Step 3: Author notebook 4 as a real workflow deliverable**

Notebook 4 must show:
- prompt construction
- security-labeled dataset shaping
- dry-run command for `rtl_analyzer/scripts/fine_tune_llm_scanner.py`
- Qwen3.5 recommendation and Unsloth-style LoRA/QLoRA notes

- [ ] **Step 4: Execute notebook 4**

Run: `cd /home/jovyan/silicogen && python -m jupyter nbconvert --to notebook --execute --inplace notebooks/rtl_analyzer_phase3/04_llm_security_scanner.ipynb`
Expected: notebook executes in place with no traceback; actual training cells remain dry-run safe on this server.

- [ ] **Step 5: Re-run the notebook test**

Run: `cd /home/jovyan/silicogen/rtl_analyzer && python -m pytest tests/test_phase3_docs.py::test_notebook_04_exists_and_mentions_qwen_and_lora -v`
Expected: PASS.

- [ ] **Step 6: Update the handoff file**

Add notebook 4 path, dry-run status, and the next GPU-server handoff action.

- [ ] **Step 7: Commit**

```bash
git add notebooks/rtl_analyzer_phase3/04_llm_security_scanner.ipynb rtl_analyzer/tests/test_phase3_docs.py docs/superpowers/context/rtl-analyzer-phase3-handoff.md
git commit -m "docs(phase3): add LLM security scanner notebook"
```

---

### Task 10: Add only an optional non-blocking graph/GNN scaffold

**Files:**
- Create: `rtl_analyzer/rtl_analyzer/ml/circuit_graph.py`
- Modify: `rtl_analyzer/rtl_analyzer/ml/classifiers.py`
- Test: `rtl_analyzer/tests/test_phase3_ml.py`
- Modify: `docs/superpowers/context/rtl-analyzer-phase3-handoff.md`

- [ ] **Step 1: Write the failing optional-graph tests**

```python
def test_graph_contract_can_load_canned_payload_without_yosys():
    payload = {"nodes": [{"id": "n1", "kind": "wire"}], "edges": []}
    graph = load_graph_payload(payload)
    assert len(graph.nodes) == 1
    assert graph.nodes[0]["id"] == "n1"


def test_require_yosys_returns_clear_deferred_message_when_missing():
    msg = require_yosys(optional=True)
    assert "deferred" in msg.lower() or "yosys" in msg.lower()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /home/jovyan/silicogen/rtl_analyzer && python -m pytest tests/test_phase3_ml.py -k graph -v`
Expected: FAIL because the optional graph scaffold does not exist yet.

- [ ] **Step 3: Implement only the stable scaffold contract**

Required behavior:
- pure payload-to-graph conversion works without Yosys
- runtime `require_yosys()` check produces a clear deferred message
- no real Yosys-backed training is required in this plan

- [ ] **Step 4: Smoke-test the current server behavior**

Run: `cd /home/jovyan/silicogen/rtl_analyzer && python -c "import shutil; print(shutil.which('yosys'))"`
Expected: `None` on this server; treat that as confirmation that real Yosys-backed GNN training remains deferred to the other server.

- [ ] **Step 5: Re-run the graph-focused tests**

Run: `cd /home/jovyan/silicogen/rtl_analyzer && python -m pytest tests/test_phase3_ml.py -k graph -v`
Expected: PASS without requiring Yosys.

- [ ] **Step 6: Update the handoff file**

Record that graph/GNN code is scaffold-only here and that real Yosys-backed GNN training is deferred to the other server.

- [ ] **Step 7: Commit**

```bash
git add rtl_analyzer/rtl_analyzer/ml/circuit_graph.py rtl_analyzer/rtl_analyzer/ml/classifiers.py rtl_analyzer/tests/test_phase3_ml.py docs/superpowers/context/rtl-analyzer-phase3-handoff.md
git commit -m "feat(phase3): add non-blocking graph scaffold"
```

---

### Task 11: Integrate engine and CLI paths, then run final verification

**Files:**
- Modify: `rtl_analyzer/rtl_analyzer/checks/__init__.py`
- Modify: `rtl_analyzer/rtl_analyzer/engine.py`
- Modify: `rtl_analyzer/rtl_analyzer/cli.py`
- Create: `rtl_analyzer/rtl_analyzer/checks/ast_classifier.py`
- Create: `rtl_analyzer/rtl_analyzer/checks/llm_scanner.py`
- Test: `rtl_analyzer/tests/test_phase3_integration.py`
- Modify: `docs/superpowers/context/rtl-analyzer-phase3-handoff.md`

- [ ] **Step 1: Write the failing integration tests**

```python
from click.testing import CliRunner

from rtl_analyzer.cli import main


def test_default_cli_path_stays_deterministic():
    runner = CliRunner()
    result = runner.invoke(main, ["tests/fixtures/clean/clean_counter.v"])
    assert result.exit_code == 0
    assert "RTL_ML" not in result.output


def test_ml_checks_require_explicit_flag_and_model_dir():
    runner = CliRunner()
    result = runner.invoke(main, ["--enable-ml", "--ml-checks", "RTL_ML002", "tests/fixtures/clean/clean_counter.v"])
    assert result.exit_code != 0
    assert "model-dir" in result.output.lower()
```

- [ ] **Step 2: Run the integration tests to verify they fail**

Run: `cd /home/jovyan/silicogen/rtl_analyzer && python -m pytest tests/test_phase3_integration.py -v`
Expected: FAIL because runtime ML checks and CLI gating are not wired yet.

- [ ] **Step 3: Add runtime AST and LLM check adapters behind explicit flags**

Required behavior:
- `RTL_ML002` and `RTL_ML003` only run when `--enable-ml` is set
- missing artifacts produce controlled configuration messages
- default deterministic registry remains the default engine path

- [ ] **Step 4: Wire CLI flags without changing the default command path**

Required CLI options:
- `--enable-ml`
- `--ml-checks RTL_ML002,RTL_ML003`
- `--model-dir /path/to/models`

- [ ] **Step 5: Re-run the focused integration tests**

Run: `cd /home/jovyan/silicogen/rtl_analyzer && python -m pytest tests/test_phase3_integration.py -v`
Expected: PASS.

- [ ] **Step 6: Run the full final verification for this server**

Run: `cd /home/jovyan/silicogen/rtl_analyzer && python -m pytest tests/test_checks.py tests/test_phase2.py tests/test_phase3_contracts.py tests/test_phase3_dataflow.py tests/test_phase3_dataset.py tests/test_phase3_docs.py tests/test_phase3_ml.py tests/test_phase3_llm.py tests/test_phase3_integration.py -v`
Expected: PASS on this server without Yosys.

- [ ] **Step 7: Run end-to-end deterministic and feature-gated smoke checks**

Run: `cd /home/jovyan/silicogen/rtl_analyzer && python -m rtl_analyzer.cli tests/fixtures/buggy/buggy_combo_loop.v --format json && python -m rtl_analyzer.cli --enable-ml --ml-checks RTL_ML002 --model-dir /tmp/rtl_phase3_models tests/fixtures/clean/clean_counter.v --format json`
Expected:
- first command reports real `RTL_E002`
- second command runs only when model artifacts exist
- if model artifacts are missing, it exits with a controlled message instead of crashing

- [ ] **Step 8: Update the handoff file with final server status**

Required final notes:
- AST baseline is the main ML success criterion on this server
- real Yosys-backed GNN training is deferred to the other server
- `RTL_E006` and `RTL_W007` enhancements are not part of this Phase 3 plan

- [ ] **Step 9: Commit**

```bash
git add rtl_analyzer/rtl_analyzer/checks/__init__.py rtl_analyzer/rtl_analyzer/engine.py rtl_analyzer/rtl_analyzer/cli.py rtl_analyzer/rtl_analyzer/checks/ast_classifier.py rtl_analyzer/rtl_analyzer/checks/llm_scanner.py rtl_analyzer/tests/test_phase3_integration.py docs/superpowers/context/rtl-analyzer-phase3-handoff.md
git commit -m "feat(phase3): integrate feature-gated ML paths"
```

---

Plan complete and saved to `docs/superpowers/plans/2026-03-24-rtl-analyzer-phase3.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
