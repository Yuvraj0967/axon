"""Validated offline loader for supervised bearing model bundles."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import joblib
import numpy as np

from ml.bearing.signal import feature_vector, validate_signal


class BearingBundleError(RuntimeError):
    pass


class RandomForestBearingBundle:
    def __init__(self, model, metadata: dict):
        self.model, self.metadata = model, metadata

    def probabilities(self, signal, sampling_frequency_hz: float) -> dict[str, float]:
        contract = self.metadata["input_contract"]
        required_frequency = float(contract["sampling_frequency_hz"])
        if not np.isclose(float(sampling_frequency_hz), required_frequency):
            raise ValueError(f"sampling frequency {sampling_frequency_hz} Hz does not match model requirement {required_frequency} Hz")
        values = validate_signal(signal, sampling_frequency_hz, minimum_samples=int(contract["window_samples"]))
        if len(values) != int(contract["window_samples"]):
            raise ValueError(f"signal window must contain exactly {contract['window_samples']} samples")
        probabilities = self.model.predict_proba(feature_vector(values, sampling_frequency_hz).reshape(1, -1))[0]
        return {label: float(probability) for label, probability in zip(self.model.named_steps["classifier"].classes_, probabilities)}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_bearing_bundle(bundle_dir: Path) -> RandomForestBearingBundle:
    bundle_dir = Path(bundle_dir); metadata_path = bundle_dir / "metadata.json"
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BearingBundleError("bearing bundle metadata is missing or invalid") from exc
    if metadata.get("bundle_schema_version") != "axon-bearing-bundle-v1":
        raise BearingBundleError("unsupported bearing bundle schema")
    if metadata.get("kind") != "bearing_random_forest":
        raise BearingBundleError("this runtime only supports validated Random Forest bearing bundles")
    artifact = metadata.get("artifact", {}); model_path = bundle_dir / str(artifact.get("filename", ""))
    if not model_path.is_file() or _sha256(model_path) != artifact.get("sha256"):
        raise BearingBundleError("bearing model artifact is missing or checksum verification failed")
    contract = metadata.get("input_contract", {})
    if contract.get("sensor_type") != "vibration" or not contract.get("feature_names") or not contract.get("window_samples"):
        raise BearingBundleError("bearing model has an incompatible input contract")
    try:
        model = joblib.load(model_path)
    except Exception as exc:
        raise BearingBundleError("bearing model artifact cannot be loaded") from exc
    if not hasattr(model, "predict_proba"):
        raise BearingBundleError("bearing model does not expose class probabilities")
    return RandomForestBearingBundle(model, metadata)
