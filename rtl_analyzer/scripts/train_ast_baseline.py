from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rtl_analyzer.ml.classifiers import AstBaselineClassifier
from rtl_analyzer.ml.dataset_manifest import DatasetEntry, read_manifest
from rtl_analyzer.ml.metrics import compute_classification_metrics, majority_vote
from rtl_analyzer.parser import parse_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the Phase 3 AST baseline.")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--model-dir", required=True, type=Path)
    parser.add_argument("--predictions-out", required=True, type=Path)
    parser.add_argument("--metrics-out", required=True, type=Path)
    parser.add_argument("--baseline-out", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = read_manifest(args.manifest)
    entries_by_split = split_entries(manifest.entries)

    train_entries = entries_by_split["train"]
    held_out_entries = entries_by_split["test"] or entries_by_split["val"]
    if not train_entries:
        raise SystemExit("manifest must contain at least one training entry")
    if not held_out_entries:
        raise SystemExit("manifest must contain at least one held-out entry")

    train_parsed = [parse_entry(args.manifest, entry) for entry in train_entries]
    held_out_parsed = [parse_entry(args.manifest, entry) for entry in held_out_entries]
    train_labels = [primary_label(entry) for entry in train_entries]
    held_out_labels = [primary_label(entry) for entry in held_out_entries]

    classifier = AstBaselineClassifier(random_state=manifest.seed)
    classifier.fit(train_parsed, train_labels)
    predictions = classifier.predict(held_out_parsed)
    probabilities = classifier.predict_proba(held_out_parsed)

    artifact_dir = args.model_dir / "ast"
    classifier.save(
        artifact_dir / "model.json",
        artifact_dir / "labels.json",
        artifact_dir / "thresholds.json",
    )

    write_predictions(
        args.predictions_out,
        held_out_entries,
        held_out_labels,
        predictions,
        probabilities,
        backend=classifier.backend,
    )

    majority_label = majority_vote(train_labels)
    majority_predictions = [majority_label for _ in held_out_labels]
    metrics_payload = {
        "seed": manifest.seed,
        "backend": classifier.backend,
        "train_count": len(train_entries),
        "held_out_count": len(held_out_entries),
        "held_out_split": held_out_entries[0].split,
        "labels": classifier.labels,
        "metrics": compute_classification_metrics(held_out_labels, predictions),
        "note": metric_note(classifier.backend),
    }
    args.metrics_out.parent.mkdir(parents=True, exist_ok=True)
    args.metrics_out.write_text(json.dumps(metrics_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    baseline_payload = {
        "strategy": "majority_label",
        "majority_label": majority_label,
        "held_out_split": held_out_entries[0].split,
        "held_out_count": len(held_out_entries),
        "metrics": compute_classification_metrics(held_out_labels, majority_predictions),
        "note": "Tiny bootstrap dataset: majority baseline is a pipeline sanity reference, not a final benchmark.",
    }
    args.baseline_out.parent.mkdir(parents=True, exist_ok=True)
    args.baseline_out.write_text(json.dumps(baseline_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


def split_entries(entries: list[DatasetEntry]) -> dict[str, list[DatasetEntry]]:
    buckets = {"train": [], "val": [], "test": []}
    for entry in entries:
        if entry.split in buckets:
            buckets[entry.split].append(entry)
    return buckets


def parse_entry(manifest_path: Path, entry: DatasetEntry):
    return parse_file(manifest_path.parent / entry.path)


def primary_label(entry: DatasetEntry) -> str:
    if not entry.labels:
        raise ValueError(f"entry {entry.sample_id} has no labels")
    return entry.labels[0]


def metric_note(backend: str) -> str:
    if backend == "xgboost":
        return "AST baseline uses XGBoost features over a tiny bootstrap dataset; treat metrics as pipeline validation only."
    return "AST baseline uses the stable scikit-learn backend in this environment; metrics validate the pipeline, not final model quality."


def write_predictions(
    path: Path,
    entries: list[DatasetEntry],
    truth: list[str],
    predictions: list[str],
    probabilities: list[dict[str, float]],
    backend: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for entry, expected, predicted, probability in zip(entries, truth, predictions, probabilities, strict=True):
            handle.write(
                json.dumps(
                    {
                        "sample_id": entry.sample_id,
                        "split": entry.split,
                        "path": entry.path,
                        "true_label": expected,
                        "predicted_label": predicted,
                        "backend": backend,
                        "probabilities": probability,
                    },
                    sort_keys=True,
                )
                + "\n"
            )


if __name__ == "__main__":
    raise SystemExit(main())
