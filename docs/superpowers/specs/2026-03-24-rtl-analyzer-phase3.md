# RTL Analyzer Phase 3 Spec

## Goal

Phase 3 extends `rtl_analyzer` in a practical order:

1. Strengthen the deterministic analyzer first.
2. Build a reusable dataflow DAG and replace the current `RTL_E002` stub with real combinational-loop detection.
3. Add a reproducible dataset and notebook workflow.
4. Ship the first real trained model as an AST + XGBoost baseline.
5. Add an LLM security-scanning path after the algorithm work and AST baseline are in place.

The default CLI path must remain fast, deterministic, and usable without ML dependencies. ML-assisted checks stay behind explicit feature flags.

## Architecture

Phase 3 is split into two lanes:

- Deterministic lane: parser -> semantic model -> shared dataflow DAG -> rule checks.
- ML lane: dataset/manifest layer -> feature extraction or prompt packing -> offline training artifacts -> optional runtime checks.

The shared dataflow DAG is the first new core abstraction. It supports the real `RTL_E002` implementation immediately and can later feed feature extraction for ML work.

On this server, Yosys is not available. Because of that, the GNN path is not the first real model deliverable and is not the main Phase 3 success criterion here. A temporary `pyslang`-derived graph interface may exist only as scaffold or test plumbing so downstream code has a stable contract. Real Yosys-backed graph extraction and GNN training are deferred to the other server where Yosys is installed.

LLM work is a later Phase 3 layer, not the foundation. It is intended for security and vulnerability scanning, not for replacing the deterministic engine.

## Scope

In scope:

- Real dataflow DAG construction.
- Real `RTL_E002` combinational-loop detection built on that DAG.
- Reproducible datasets with provenance and stable splits.
- Notebooks that act as both reproducibility tools and lightweight tutorials.
- A persistent context/handoff file so work can continue across servers and sessions.
- AST feature extraction and an XGBoost baseline as the first trained model.
- A deferred-ready GNN interface that can be scaffolded and tested without making Yosys the blocking dependency on this server.
- An LLM security scanner path with Qwen3.5-family fine-tuning as the recommended direction.

Out of scope for this spec's deliverables:

- Real Yosys-backed GNN training on this server.
- Treating the GNN as the first production model.
- Broad autonomous data collection or scraping.
- Making ML checks part of the default analyzer path.
- `RTL_E006` and `RTL_W007` Phase 3 enhancements, except for incidental shared algorithm work that naturally helps future phases.

`RTL_E006` and `RTL_W007` expansion is explicitly deferred to a later Phase 3B and should not be counted as a deliverable for this document.

## Deliverables

Phase 3 deliverables are ordered by dependency and priority:

1. Shared dataflow DAG and a real `RTL_E002` implementation.
2. Dataset manifest and reproducible dataset build flow.
3. Notebook set for reproduction, inspection, and onboarding.
4. Persistent context/handoff file and update convention.
5. AST + XGBoost baseline training, evaluation, and optional runtime hook.
6. LLM security-scanning dataset format, prompt/inference path, and fine-tuning workflow definition.
7. Optional graph/GNN scaffold that preserves a future Yosys-backed path without making it the current milestone.

Success for this phase is primarily defined by the algorithm work and the AST baseline, not by GNN completion.

## File map

The exact implementation may adjust filenames, but Phase 3 should introduce or reserve space for the following categories:

- `rtl_analyzer/dataflow.py` - shared DAG construction, traversal, and cycle analysis.
- `rtl_analyzer/checks/combinational_loop.py` - real `RTL_E002` logic backed by the DAG.
- `rtl_analyzer/ml/dataset_manifest.py` - manifest schema, provenance, split metadata.
- `rtl_analyzer/ml/ast_features.py` - AST-level feature extraction for the first trained model.
- `rtl_analyzer/ml/classifiers.py` - baseline XGBoost training/inference support; optional later graph model hooks.
- `rtl_analyzer/ml/circuit_graph.py` - temporary graph interface and future Yosys-backed bridge.
- `rtl_analyzer/ml/vulnerability_scanner.py` - LLM prompt packing, dataset shaping, and inference/fine-tuning helpers.
- `scripts/build_phase3_dataset.py` - reproducible dataset build entry point.
- `scripts/train_ast_baseline.py` - first real training entry point.
- `scripts/evaluate_phase3.py` - evaluation and report generation.
- `scripts/fine_tune_llm_scanner.py` - security-scanner fine-tuning workflow entry point.
- `notebooks/rtl_analyzer_phase3/01_dataflow_and_rtl_e002.ipynb` - algorithm and DAG walkthrough.
- `notebooks/rtl_analyzer_phase3/02_dataset_build_and_inspection.ipynb` - manifest and split reproduction.
- `notebooks/rtl_analyzer_phase3/03_ast_xgboost_baseline.ipynb` - baseline training and analysis.
- `notebooks/rtl_analyzer_phase3/04_llm_security_scanner.ipynb` - prompt format, labels, and fine-tuning/inference walkthrough.
- `docs/superpowers/context/rtl-analyzer-phase3-handoff.md` - persistent cross-session context file.

## Model strategy

The model strategy is intentionally staged.

First real model:

- AST + XGBoost is the first trained model deliverable.
- It is chosen because it can be trained and evaluated on this server without Yosys.
- It provides a practical baseline before any heavier graph or LLM work.

Graph/GNN path:

- A temporary `pyslang` graph path may exist only as scaffold, interface validation, or tests.
- That path should not be treated as the final graph source of truth.
- Real graph extraction for training should be Yosys-backed and is deferred to the other server where Yosys is available.
- Any GNN code added in Phase 3 should be clearly feature-gated and dependency-aware.

LLM path:

- LLM work starts only after the algorithm layer and AST baseline are established.
- Recommended base models are from the Qwen3.5 family.
- Recommended fine-tuning workflow is Unsloth-style LoRA or QLoRA, chosen for practical GPU fine-tuning and adapter-based deployment.
- The LLM's purpose is security and vulnerability scanning with structured outputs such as CWE-style labels, short rationale, and likely line hints.
- The LLM is an additive assistant path, not the default engine and not a replacement for deterministic checks.

Runtime behavior:

- Deterministic analysis remains the default and fastest path.
- ML paths remain behind feature flags and explicit model configuration.
- Missing optional dependencies should degrade cleanly with clear messages rather than affecting base analyzer use.

## Dataset strategy

The dataset layer should support both deterministic reproducibility and future model work.

- Use a manifest-driven dataset with stable sample IDs, provenance, labels, and split assignment.
- Support mixed sources, including synthetic examples and local external corpora.
- Record enough metadata to reproduce a dataset build on another server.
- Keep the security-scanner dataset contract separate enough to store CWE-style labels, rationale text, and line-level hints when available.
- Preserve a path for graph-oriented assets later, but do not make graph extraction the prerequisite for the first usable dataset.

The initial dataset emphasis is:

1. Samples that validate the new algorithm work, especially real `RTL_E002` behavior.
2. Samples sufficient for the AST baseline.
3. Security-labeled samples for later LLM work.

## Evaluation strategy

Evaluation should stay plain, repeatable, and easy to compare across sessions.

- Measure deterministic correctness first for the dataflow DAG and `RTL_E002`.
- Evaluate the AST baseline against a simple baseline such as majority-class prediction.
- Track metrics by split and source type so synthetic-only gains do not hide weak real-data behavior.
- Keep threshold selection and report generation reproducible from saved artifacts.
- Treat LLM evaluation separately from generic bug classification: security-label quality, rationale usefulness, and line-hint usefulness matter more than a single binary score.

The practical acceptance order is:

1. Correct algorithm behavior.
2. Reproducible dataset and reports.
3. AST baseline that is meaningfully better than trivial prediction.
4. LLM security-scanner evaluation once labeled security data is ready.

## Notebook strategy

Phase 3 notebooks are first-class deliverables.

They serve two purposes at the same time:

- Reproducibility tools for rerunning dataset, feature, and evaluation flows.
- Lightweight tutorials for future contributors who need to understand the system quickly.

Each notebook should be small, task-focused, and runnable in order. They should prefer loading saved artifacts over embedding large amounts of custom notebook-only logic. The notebooks should explain what was produced, where artifacts live, and how to rerun the corresponding script path.

## Context-file strategy

Phase 3 should include a persistent handoff file at `docs/superpowers/context/rtl-analyzer-phase3-handoff.md`.

Its purpose is to preserve continuity across servers and sessions. It should be lightweight and updated as work progresses. At minimum it should track:

- current status by deliverable;
- environment notes, especially whether Yosys is available;
- latest dataset and model artifact locations;
- open questions and deferred items;
- next recommended actions;
- differences between this server and the Yosys-capable server.

This file is operational context, not polished documentation. It should be easy to append to and easy for a later worker to trust.

## Known limitations

- Yosys is not installed on this server, so real Yosys-backed graph extraction and GNN training are deferred.
- Any temporary `pyslang` graph path is only a scaffold or compatibility layer, not the target long-term graph pipeline.
- Security-label coverage may lag behind generic bug labels, which limits immediate LLM fine-tuning quality.
- LLM outputs for rationale and line hints will require careful evaluation because usefulness is not captured by a single classifier metric.
- `RTL_E006` and `RTL_W007` enhancements are deferred to Phase 3B and are not Phase 3 success criteria here.

## Practical phase boundary

If Phase 3 ends with a solid dataflow DAG, a real `RTL_E002`, reproducible notebooks and datasets, a maintained handoff file, and an AST + XGBoost baseline, it has met its main goal on this server. GNN training and broader check expansion can continue later on the Yosys-capable environment without redefining this phase.
