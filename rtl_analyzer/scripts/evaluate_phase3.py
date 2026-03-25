from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rtl_analyzer.ml.dataset_manifest import DatasetEntry, read_manifest
from rtl_analyzer.ml.metrics import compute_classification_metrics, majority_vote


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate Phase 3 held-out predictions.")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--predictions", required=True, type=Path)
    parser.add_argument("--report-out", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = evaluate_predictions(args.manifest, args.predictions)
    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    args.report_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


def evaluate_predictions(manifest_path: Path, predictions_path: Path) -> dict[str, object]:
    manifest = read_manifest(manifest_path)
    held_out_entries = [entry for entry in manifest.entries if entry.split == "test"]
    if not held_out_entries:
        held_out_entries = [entry for entry in manifest.entries if entry.split == "val"]
    if not held_out_entries:
        raise ValueError("manifest must contain a held-out split")

    truth_by_sample = {entry.sample_id: primary_label(entry) for entry in held_out_entries}
    predictions = read_predictions(predictions_path)

    expected_ids = sorted(truth_by_sample)
    prediction_ids = sorted(predictions)
    missing_ids = sorted(set(expected_ids) - set(prediction_ids))
    extra_ids = sorted(set(prediction_ids) - set(expected_ids))
    if missing_ids:
        raise ValueError(f"missing held-out predictions: {', '.join(missing_ids)}")
    if extra_ids:
        raise ValueError(f"unexpected held-out predictions: {', '.join(extra_ids)}")

    y_true = [truth_by_sample[sample_id] for sample_id in expected_ids]
    y_pred = [str(predictions[sample_id]["predicted_label"]) for sample_id in expected_ids]
    train_labels = [primary_label(entry) for entry in manifest.entries if entry.split == "train"]
    majority_label = majority_vote(train_labels)
    majority_predictions = [majority_label for _ in y_true]
    backend_names = sorted({str(predictions[sample_id].get("backend", "unknown")) for sample_id in expected_ids})

    return {
        "held_out_split": held_out_entries[0].split,
        "held_out_count": len(expected_ids),
        "integrity": {
            "extra_prediction_ids": extra_ids,
            "missing_prediction_ids": missing_ids,
            "matched_prediction_ids": expected_ids,
        },
        "ast_baseline": {
            "backend": backend_names[0] if len(backend_names) == 1 else ",".join(backend_names),
            "metrics": compute_classification_metrics(y_true, y_pred),
        },
        "majority_baseline": {
            "label": majority_label,
            "metrics": compute_classification_metrics(y_true, majority_predictions),
        },
        "note": "This Phase 3 report is based on a tiny bootstrap dataset and is suitable for pipeline validation, not broad performance claims.",
    }


def read_predictions(path: Path) -> dict[str, dict[str, object]]:
    predictions: dict[str, dict[str, object]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        predictions[str(payload["sample_id"])] = payload
    return predictions


def primary_label(entry: DatasetEntry) -> str:
    if not entry.labels:
        raise ValueError(f"entry {entry.sample_id} has no labels")
    return entry.labels[0]


if __name__ == "__main__":
    raise SystemExit(main())
