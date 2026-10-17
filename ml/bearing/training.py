"""Leakage-resistant supervised bearing-model training helpers."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import time

import joblib
import numpy as np
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import balanced_accuracy_score, classification_report, confusion_matrix, f1_score, log_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ml.bearing.signal import FEATURE_VERSION, feature_names, feature_vector, validate_signal
from ml.bearing.taxonomy import TAXONOMY_VERSION


def load_prepared(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    data = np.load(path, allow_pickle=False)
    required = {"signals", "labels", "groups", "sampling_frequency_hz"}
    if not required.issubset(data.files):
        raise ValueError("prepared data is missing signals, labels, groups, or sampling_frequency_hz")
    signals, labels, groups = data["signals"], data["labels"].astype(str), data["groups"].astype(str)
    if signals.ndim != 2 or not len(signals) or len(signals) != len(labels) or len(labels) != len(groups):
        raise ValueError("prepared data arrays have incompatible shapes")
    sampling_frequency = float(data["sampling_frequency_hz"])
    for signal in signals:
        validate_signal(signal, sampling_frequency, minimum_samples=signals.shape[1])
    return signals.astype(np.float64), labels, groups, sampling_frequency


def grouped_split(labels: np.ndarray, groups: np.ndarray, *, seed: int = 42) -> dict[str, np.ndarray]:
    """Create a class-balanced split whose groups are physical bearings.

    A bearing has a single fault label.  Requiring three independent bearings
    for every represented class places one whole bearing in each partition and
    avoids both window and operating-condition leakage.
    """
    if len(labels) != len(groups):
        raise ValueError("labels and groups must have the same length")
    group_labels: dict[str, str] = {}
    for group in np.unique(groups):
        labels_for_group = np.unique(labels[groups == group])
        if len(labels_for_group) != 1:
            raise ValueError(f"physical-bearing group {group!r} has conflicting labels")
        group_labels[str(group)] = str(labels_for_group[0])
    by_class: dict[str, list[str]] = {}
    for group, label in group_labels.items():
        by_class.setdefault(label, []).append(group)
    inadequate = {label: len(items) for label, items in by_class.items() if len(items) < 3}
    if inadequate:
        details = ", ".join(f"{label}={count}" for label, count in sorted(inadequate.items()))
        raise ValueError("unseen-bearing evaluation requires at least three physical bearings per class; found " + details)
    rng = np.random.default_rng(seed)
    selected: dict[str, list[str]] = {"train": [], "validation": [], "test": []}
    for label in sorted(by_class):
        candidates = np.asarray(sorted(by_class[label]), dtype=str)
        rng.shuffle(candidates)
        selected["test"].append(candidates[0])
        selected["validation"].append(candidates[1])
        selected["train"].extend(candidates[2:].tolist())
    return {name: np.flatnonzero(np.isin(groups, selected_groups)) for name, selected_groups in selected.items()}


def _metrics(true: np.ndarray, predicted: np.ndarray, probabilities: np.ndarray, classes: np.ndarray) -> dict:
    return {"macro_f1": float(f1_score(true, predicted, average="macro", zero_division=0)), "balanced_accuracy": float(balanced_accuracy_score(true, predicted)), "classification_report": classification_report(true, predicted, labels=classes, output_dict=True, zero_division=0), "confusion_matrix": confusion_matrix(true, predicted, labels=classes).tolist(), "classes": classes.tolist(), "multiclass_log_loss": float(log_loss(true, probabilities, labels=classes))}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def train_random_forest(prepared_path: Path, output_dir: Path, *, seed: int = 42, trees: int = 200) -> dict:
    signals, labels, groups, sampling_frequency = load_prepared(prepared_path)
    split = grouped_split(labels, groups, seed=seed)
    features = np.asarray([feature_vector(window, sampling_frequency) for window in signals])
    if len(np.unique(labels[split["train"]])) < 2:
        raise ValueError("training partition needs at least two fault classes")
    model = Pipeline([("scaler", StandardScaler()), ("classifier", RandomForestClassifier(n_estimators=trees, random_state=seed, class_weight="balanced_subsample", n_jobs=1))])
    started = time.perf_counter()
    model.fit(features[split["train"]], labels[split["train"]])
    duration = time.perf_counter() - started
    classes = model.named_steps["classifier"].classes_
    test_probabilities = model.predict_proba(features[split["test"]])
    test_predictions = model.predict(features[split["test"]])
    output_dir = Path(output_dir); output_dir.mkdir(parents=True, exist_ok=True)
    model_path = output_dir / "model.joblib"; joblib.dump(model, model_path)
    metadata = {"bundle_schema_version": "axon-bearing-bundle-v1", "kind": "bearing_random_forest", "model_version": "axon-bearing-rf-v1", "created_at": datetime.now(timezone.utc).isoformat(), "taxonomy_version": TAXONOMY_VERSION, "preprocessing_version": FEATURE_VERSION, "input_contract": {"sensor_type": "vibration", "sampling_frequency_hz": sampling_frequency, "window_samples": int(signals.shape[1]), "feature_names": list(feature_names())}, "classes": classes.tolist(), "split": {name: {"windows": int(len(indices)), "groups": sorted(np.unique(groups[indices]).tolist())} for name, indices in split.items()}, "training": {"seed": seed, "trees": trees, "duration_seconds": duration, "library_versions": {"python": platform.python_version(), "scikit_learn": sklearn.__version__}}, "source": {"prepared_path": str(prepared_path), "sha256": _sha256(Path(prepared_path))}, "artifact": {"filename": model_path.name, "sha256": _sha256(model_path)}}
    report = _metrics(labels[split["test"]], test_predictions, test_probabilities, classes) | {"evaluation_unit": "windows from held-out physical bearings", "warning": "Metrics are valid only for the prepared dataset and its held-out physical-bearing split."}
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    (output_dir / "evaluation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return metadata | {"evaluation": report}
