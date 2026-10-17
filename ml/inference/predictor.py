"""Trusted Axon model-artifact loader and calibrated inference interface."""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np


FEATURES = ("temp", "vibration", "current")


class ArtifactLoadError(RuntimeError):
    """Raised when a local, trusted artifact is incomplete or incompatible."""


class Predictor:
    def __init__(self, pipeline, metadata):
        self.pipeline = pipeline
        self.metadata = metadata

    def predict_one(self, observation):
        try:
            values = np.asarray([[float(observation[name]) for name in FEATURES]], dtype=float)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("observation must contain finite temp, vibration, and current values") from exc
        if not np.isfinite(values).all():
            raise ValueError("observation contains non-finite feature values")
        # Higher values are more anomalous: negative decision_function is inverted.
        anomaly_score = float(-self.pipeline.decision_function(values)[0])
        return {
            "anomaly_score": round(anomaly_score, 6),
            "is_anomaly": anomaly_score >= float(self.metadata["threshold"]),
            "model_version": self.metadata["model_version"],
        }


def load_predictor(artifact_dir):
    artifact_dir = Path(artifact_dir)
    model_path = artifact_dir / "model.joblib"
    metadata_path = artifact_dir / "metadata.json"
    if not model_path.is_file() or not metadata_path.is_file():
        raise ArtifactLoadError(f"required model files are missing in {artifact_dir}")
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtifactLoadError("metadata.json is invalid") from exc
    required = {"model_version", "features", "threshold", "scoring_convention"}
    missing = required - set(metadata)
    if missing or tuple(metadata.get("features", ())) != FEATURES:
        raise ArtifactLoadError("artifact metadata has missing or incompatible feature definitions")
    if not isinstance(metadata["threshold"], (int, float)) or not np.isfinite(metadata["threshold"]):
        raise ArtifactLoadError("artifact threshold is invalid")
    try:
        pipeline = joblib.load(model_path)
    except Exception as exc:  # trusted artifacts only; preserve a clear failure for corrupt files
        raise ArtifactLoadError("trusted model artifact could not be loaded") from exc
    predictor = Predictor(pipeline, metadata)
    try:
        predictor.predict_one({"temp": 75, "vibration": 0.3, "current": 4.5})
    except Exception as exc:
        raise ArtifactLoadError("artifact inference validation failed") from exc
    return predictor
