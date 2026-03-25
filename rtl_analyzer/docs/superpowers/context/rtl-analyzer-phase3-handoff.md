# RTL Analyzer Phase 3 Handoff

**Last Updated:** 2026-03-25
**Status:** Phase 3 ML tasks complete, merged to main branch

## Status

| Task | Description | Status |
|------|-------------|--------|
| Task 1 | Phase 3 contracts and feature flags | ✓ Complete |
| Task 2 | Shared dataflow DAG + RTL_E002 | ✓ Complete |
| Task 3 | Persistent handoff file | ✓ Complete |
| Task 4 | Dataset manifest and build flow | ✓ Complete |
| Task 5 | Notebook 01 (dataflow/RTL_E002) | ✓ Complete |
| Task 6 | AST features + XGBoost baseline | ✓ Complete |
| Task 7 | Notebooks 02/03 (dataset + AST) | ✓ Complete |
| **GPU ML Tasks** | | |
| Task GPU-0 | GPU verification (Tesla T4) | ✓ Complete |
| Task GPU-1 | RTL Bug Classification (XGBoost) | ✓ Complete (95.5%) |
| Task GPU-2 | Combined dataset (719 samples) | ✓ Complete |
| Task GPU-3 | Security Detection (PyTorch) | ✓ Complete (75.0%) |
| Task GPU-4 | Quality Prediction (Multi-task) | ✓ Complete (49.3%) |
| Task 8 | LLM security scanner | ⏳ Pending |
| Task 9 | Notebook 04 (LLM workflow) | ⏳ Pending |
| Task 10 | GNN scaffold | ⏳ Deferred |
| Task 11 | Final verification | ⏳ Pending |

## Environment Notes

- **Server:** Ubuntu with Tesla T4 (14.6 GB VRAM), CUDA 13.0
- **Python:** 3.12
- **Key packages:** pyslang 10.0.0, xgboost 3.2.0, torch 2.11.0+cu130, scikit-learn 1.7.2
- **Yosys:** Unavailable (GNN training deferred)
- **Default path:** Deterministic (no ML dependencies required)

## Project Structure

```
/home/jovyan/silicogen/rtl_analyzer/
├── rtl_analyzer/
│   ├── __init__.py
│   ├── models.py          # CheckID enum (includes RTL_ML001-003)
│   ├── engine.py          # AnalysisEngine
│   ├── cli.py             # CLI with --enable-ml flag
│   ├── parser/
│   ├── checks/
│   │   ├── combinational_loop.py  # Real RTL_E002 with dataflow
│   │   └── ...
│   ├── dataflow.py        # Signal dependency DAG (NEW)
│   └── ml/                # NEW
│       ├── __init__.py
│       ├── ast_features.py
│       ├── classifiers.py
│       ├── dataset_manifest.py
│       └── metrics.py
├── dataset/               # NEW
│   ├── manifest.json
│   ├── dataset.csv, train.csv, val.csv, test.csv
├── models/                # NEW
│   ├── rtl_bug_classifier.json
│   ├── security_classifier.pt
│   └── quality_predictor.pt
├── notebooks/rtl_analyzer_phase3/  # NEW
│   ├── 00_gpu_verification.ipynb
│   ├── 04_rtl_bug_classification.ipynb
│   ├── 05_build_combined_dataset.ipynb
│   ├── 06_security_detection.ipynb
│   └── 07_quality_prediction.ipynb
├── scripts/               # NEW
│   ├── build_phase3_dataset.py
│   ├── build_combined_dataset.py
│   ├── train_ast_baseline.py
│   └── evaluate_phase3.py
├── tests/
│   ├── test_phase3_contracts.py
│   ├── test_phase3_dataflow.py
│   ├── test_phase3_dataset.py
│   ├── test_phase3_ml.py
│   └── test_phase3_docs.py
├── third_party/rtl_corpora/  # NEW
│   ├── ibex/ (~646 files)
│   ├── serv/ (~77 files)
│   ├── verilog-ethernet/ (~461 files)
│   ├── wb2axip/ (~87 files)
│   ├── secworks-sha256/ (~12 files)
│   └── pulp-axi/ (~93 files)
└── docs/superpowers/
    ├── context/rtl-analyzer-phase3-handoff.md
    └── ...
```

## Dataset Summary

| Metric | Value |
|--------|-------|
| **Total samples** | 719 |
| **Buggy** | 349 (48.5%) |
| **Clean** | 370 (51.5%) |
| **Train** | 503 |
| **Val** | 108 |
| **Test** | 108 |
| **External corpus** | 1,335 files analyzed |
| **Source repos** | 6 (ibex, serv, verilog-ethernet, wb2axip, secworks-sha256, pulp-axi) |

## ML Model Results

| Model | GPU | Accuracy | F1 | Notes |
|-------|-----|----------|-----|-------|
| **RTL Bug Classifier** | XGBoost (GPU) | 95.5% | 0.667 | 10 features, detects buggy vs clean |
| **Security Detector** | PyTorch MLP | 75.0% | 0.716 | 2-layer network (64→32→2) |
| **Quality Predictor** | PyTorch Multi-task | 49.3% | 0.33 | 4 tasks (3 regression + 1 classification) |

## Deferred Work

1. **Yosys-backed GNN training** - Deferred to server with Yosys installed
2. **LLM security scanner** (Task 8/9) - Qwen3.5 + Unsloth fine-tuning workflow
3. **Real security labels** - Current dataset uses analyzer findings as proxy labels
4. **Human-labeled quality metrics** - Quality prediction uses synthetic metrics

## Update Rule

- Update this file at the end of every completed Phase 3 task
- Record artifact paths, environment gaps, deferred items, and next recommended action

## Next Recommended Actions

1. **Task 8:** Implement LLM security scanner with Qwen3.5 + Unsloth-style LoRA/QLoRA
2. **Task 9:** Create Notebook 04 for LLM workflow demonstration
3. **Task 10:** Add optional GNN scaffold (non-blocking, Yosys deferred)
4. **Task 11:** Run final verification suite and integration tests
