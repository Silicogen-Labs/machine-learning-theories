import json
from pathlib import Path

import pytest

from rtl_analyzer.ml.ast_features import extract_ast_features
from rtl_analyzer.ml.classifiers import AstBaselineClassifier
from rtl_analyzer.ml.dataset_manifest import DatasetEntry, write_manifest
from rtl_analyzer.parser import parse_file
from scripts.evaluate_phase3 import evaluate_predictions
from scripts.train_ast_baseline import write_predictions


FIXTURES = Path(__file__).parent / "fixtures"


def test_ast_features_include_dataflow_counts():
    parsed = parse_file(FIXTURES / "clean" / "clean_counter.v")

    features = extract_ast_features(parsed)

    assert "always_block_count" in features
    assert "assign_count" in features
    assert "dataflow_cycle_count" in features


def test_ast_features_are_numeric_and_stable_for_parseable_fixture():
    parsed = parse_file(FIXTURES / "buggy" / "buggy_combo_loop.v")

    features = extract_ast_features(parsed)

    assert set(features) >= {
        "always_block_count",
        "assign_count",
        "dataflow_node_count",
        "dataflow_cycle_count",
        "module_count",
        "parse_error_count",
        "dataflow_error",
    }
    assert isinstance(features["dataflow_error"], float)
    numeric_features = {key: value for key, value in features.items() if key != "dataflow_error"}
    assert all(isinstance(value, float) for value in numeric_features.values())
    assert features["assign_count"] == 3.0
    assert features["dataflow_cycle_count"] >= 1.0
    assert features["dataflow_error"] == 0.0


def test_ast_features_record_dataflow_extraction_failure(monkeypatch):
    parsed = parse_file(FIXTURES / "clean" / "clean_counter.v")

    def boom(_parsed_file):
        raise RuntimeError("dataflow unavailable")

    monkeypatch.setattr("rtl_analyzer.ml.ast_features.build_dataflow_graph", boom)

    features = extract_ast_features(parsed)

    assert features["dataflow_error"] == 1.0
    assert features["dataflow_node_count"] == 0.0
    assert features["dataflow_cycle_count"] == 0.0


def test_ast_classifier_reports_backend_and_probabilities():
    samples = [
        (parse_file(FIXTURES / "clean" / "clean_counter.v"), "clean"),
        (parse_file(FIXTURES / "buggy" / "buggy_combo_loop.v"), "buggy"),
        (parse_file(FIXTURES / "clean" / "clean_registered_feedback.v"), "clean"),
    ]
    classifier = AstBaselineClassifier()

    classifier.fit([parsed for parsed, _ in samples], [label for _, label in samples])
    predictions = classifier.predict([parsed for parsed, _ in samples])
    probabilities = classifier.predict_proba([parsed for parsed, _ in samples])

    assert classifier.backend == classifier.backend_name
    assert classifier.backend_name == "sklearn_random_forest"
    assert len(predictions) == len(samples)
    assert set(predictions) <= {"clean", "buggy"}
    assert len(probabilities) == len(samples)
    assert set(probabilities[0]) == {"clean", "buggy"}
    assert all(0.0 <= score <= 1.0 for row in probabilities for score in row.values())


def test_evaluate_predictions_rejects_missing_held_out_ids(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    dataset_root = tmp_path / "dataset"
    dataset_root.mkdir()

    source_a = dataset_root / "train_sample.v"
    source_b = dataset_root / "test_sample.v"
    fixture_source = (FIXTURES / "clean" / "clean_counter.v").read_text(encoding="utf-8")
    source_a.write_text(fixture_source, encoding="utf-8")
    source_b.write_text(fixture_source, encoding="utf-8")

    write_manifest(
        manifest_path,
        [
            DatasetEntry(
                sample_id="train-1",
                source_group="g-train",
                source_type="synthetic",
                path="dataset/train_sample.v",
                labels=["clean"],
                split="train",
            ),
            DatasetEntry(
                sample_id="test-1",
                source_group="g-test",
                source_type="synthetic",
                path="dataset/test_sample.v",
                labels=["clean"],
                split="test",
            ),
        ],
        seed=7,
    )

    predictions_path = tmp_path / "predictions.jsonl"
    predictions_path.write_text(
        json.dumps(
            {
                "sample_id": "extra-id",
                "split": "test",
                "path": "dataset/test_sample.v",
                "true_label": "clean",
                "predicted_label": "clean",
                "probabilities": {"clean": 1.0},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="missing held-out predictions"):
        evaluate_predictions(manifest_path, predictions_path)


def test_evaluate_predictions_reports_backend_and_integrity(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    dataset_root = tmp_path / "dataset"
    dataset_root.mkdir()

    source_a = dataset_root / "train_sample.v"
    source_b = dataset_root / "test_sample.v"
    fixture_source = (FIXTURES / "clean" / "clean_counter.v").read_text(encoding="utf-8")
    source_a.write_text(fixture_source, encoding="utf-8")
    source_b.write_text(fixture_source, encoding="utf-8")

    write_manifest(
        manifest_path,
        [
            DatasetEntry(
                sample_id="train-1",
                source_group="g-train",
                source_type="synthetic",
                path="dataset/train_sample.v",
                labels=["clean"],
                split="train",
            ),
            DatasetEntry(
                sample_id="test-1",
                source_group="g-test",
                source_type="synthetic",
                path="dataset/test_sample.v",
                labels=["clean"],
                split="test",
            ),
        ],
        seed=7,
    )

    predictions_path = tmp_path / "predictions.jsonl"
    predictions_path.write_text(
        json.dumps(
            {
                "sample_id": "test-1",
                "split": "test",
                "path": "dataset/test_sample.v",
                "true_label": "clean",
                "predicted_label": "clean",
                "backend": "sklearn_random_forest",
                "probabilities": {"clean": 1.0},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    report = evaluate_predictions(manifest_path, predictions_path)

    assert report["ast_baseline"]["backend"] == "sklearn_random_forest"
    assert report["integrity"] == {
        "extra_prediction_ids": [],
        "missing_prediction_ids": [],
        "matched_prediction_ids": ["test-1"],
    }


def test_write_predictions_uses_explicit_backend_value(tmp_path):
    output_path = tmp_path / "predictions.jsonl"
    entry = DatasetEntry(
        sample_id="sample-1",
        source_group="g-1",
        source_type="synthetic",
        path="dataset/sample.v",
        labels=["clean"],
        split="test",
    )

    write_predictions(
        output_path,
        [entry],
        ["clean"],
        ["clean"],
        [{"clean": 1.0}],
        backend="xgboost",
    )

    payload = json.loads(output_path.read_text(encoding="utf-8").strip())

    assert isinstance(payload, dict)
    backend = payload.get("backend")
    assert backend == "xgboost"
