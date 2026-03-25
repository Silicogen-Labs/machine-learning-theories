from __future__ import annotations

from base64 import b64encode
import json
import pickle
from pathlib import Path
from typing import Any

import numpy as np

from rtl_analyzer.ml.ast_features import extract_ast_features

try:
    from xgboost import XGBClassifier
except ImportError:  # pragma: no cover - exercised by environment-dependent tests
    XGBClassifier = None

try:
    from sklearn.ensemble import RandomForestClassifier
except ImportError:  # pragma: no cover
    RandomForestClassifier = None


class AstBaselineClassifier:
    def __init__(self, random_state: int = 0) -> None:
        self.random_state = random_state
        self.backend = "sklearn_random_forest"
        self.backend_name = "sklearn_random_forest"
        self.model: Any | None = None
        self.feature_names: list[str] = []
        self.labels: list[str] = []

    def fit(self, parsed_files: list[Any], labels: list[str]) -> "AstBaselineClassifier":
        if not parsed_files:
            raise ValueError("at least one parsed file is required")
        if len(parsed_files) != len(labels):
            raise ValueError("parsed_files and labels must be the same length")

        matrix = self._feature_matrix(parsed_files, fit=True)
        self.labels = sorted({label for label in labels})
        label_to_index = {label: index for index, label in enumerate(self.labels)}
        encoded = np.asarray([label_to_index[label] for label in labels], dtype=np.int64)

        if XGBClassifier is not None and self.backend_name == "xgboost":
            self.backend = "xgboost"
            objective = "multi:softprob" if len(self.labels) > 2 else "binary:logistic"
            self.model = XGBClassifier(
                objective=objective,
                num_class=len(self.labels) if len(self.labels) > 2 else None,
                n_estimators=32,
                max_depth=3,
                learning_rate=0.1,
                subsample=1.0,
                colsample_bytree=1.0,
                reg_lambda=1.0,
                random_state=self.random_state,
                eval_metric="mlogloss" if len(self.labels) > 2 else "logloss",
            )
            self.model.fit(matrix, encoded)
            return self

        if RandomForestClassifier is None:
            raise RuntimeError("neither xgboost nor scikit-learn is available")

        self.backend = "sklearn_random_forest"
        self.backend_name = self.backend
        self.model = RandomForestClassifier(n_estimators=64, random_state=self.random_state)
        self.model.fit(matrix, encoded)
        return self

    def predict(self, parsed_files: list[Any]) -> list[str]:
        encoded = self._predict_encoded(parsed_files)
        return [self.labels[index] for index in encoded]

    def predict_proba(self, parsed_files: list[Any]) -> list[dict[str, float]]:
        if self.model is None:
            raise RuntimeError("classifier is not fitted")

        matrix = self._feature_matrix(parsed_files, fit=False)
        probabilities = np.asarray(self.model.predict_proba(matrix), dtype=float)
        return [
            {label: float(row[index]) for index, label in enumerate(self.labels)}
            for row in probabilities
        ]

    def save(self, model_path: Path, labels_path: Path, thresholds_path: Path) -> None:
        if self.model is None:
            raise RuntimeError("classifier is not fitted")

        model_path.parent.mkdir(parents=True, exist_ok=True)
        labels_path.parent.mkdir(parents=True, exist_ok=True)
        thresholds_path.parent.mkdir(parents=True, exist_ok=True)

        labels_path.write_text(json.dumps(self.labels, indent=2) + "\n", encoding="utf-8")
        thresholds_path.write_text(
            json.dumps({label: 0.5 for label in self.labels}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        if self.backend == "xgboost":
            self.model.save_model(str(model_path))
            return

        payload = {
            "backend": self.backend,
            "feature_names": self.feature_names,
            "labels": self.labels,
            "pickle_b64": b64encode(pickle.dumps(self.model)).decode("ascii"),
            "note": "Stable Phase 3 baseline uses scikit-learn random forest in this environment; XGBoost remains optional, not silent.",
        }
        model_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def _predict_encoded(self, parsed_files: list[Any]) -> list[int]:
        if self.model is None:
            raise RuntimeError("classifier is not fitted")
        matrix = self._feature_matrix(parsed_files, fit=False)
        predictions = self.model.predict(matrix)
        return [int(value) for value in np.asarray(predictions).tolist()]

    def _feature_matrix(self, parsed_files: list[Any], *, fit: bool) -> np.ndarray:
        feature_rows = [extract_ast_features(parsed_file) for parsed_file in parsed_files]
        if fit:
            feature_names = sorted(feature_rows[0])
            for feature_row in feature_rows[1:]:
                feature_names = sorted(set(feature_names) | set(feature_row))
            self.feature_names = feature_names
        if not self.feature_names:
            raise RuntimeError("feature names are unavailable; fit the classifier first")

        return np.asarray(
            [[feature_row.get(name, 0.0) for name in self.feature_names] for feature_row in feature_rows],
            dtype=float,
        )
