"""Healthy-only baseline: learn one machine's normal vibration and flag drift.

Small factories have no labelled failure history, so this detector is fitted
only on windows recorded while a machine runs normally. It needs no fault
labels. An Isolation Forest (Liu, Ting and Zhou, 2008) scores how unusual a new
window is, and robust per-feature deviations say which measurements changed.

A baseline belongs to one machine and one sensor mounting. It reports "changed
from this machine's normal"; it does not name a fault or predict a failure date.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform

import joblib
import numpy as np
import sklearn
from sklearn.ensemble import IsolationForest

from ml.bearing.signal import FEATURE_VERSION, feature_names, feature_vector, validate_signal

BASELINE_SCHEMA = "axon-healthy-baseline-v1"
BASELINE_KIND = "bearing_healthy_baseline"
MINIMUM_HEALTHY_WINDOWS = 40
_MAD_TO_SIGMA = 1.4826


class HealthyBaselineError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _robust_scale(features: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    center = np.median(features, axis=0)
    scale = _MAD_TO_SIGMA * np.median(np.abs(features - center), axis=0)
    fallback = features.std(axis=0)
    scale = np.where(scale > 0, scale, fallback)
    # A feature that never varied in healthy running gets a floor tied to its
    # own magnitude, so a later change is still visible without dividing by zero.
    scale = np.where(scale > 0, scale, np.maximum(np.abs(center) * 1e-3, 1e-12))
    return center, scale


class HealthyBaseline:
    """One machine's fitted normal behaviour."""

    def __init__(self, model: IsolationForest, metadata: dict):
        self.model, self.metadata = model, metadata
        self._center = np.asarray(metadata["robust_center"], dtype=np.float64)
        self._scale = np.asarray(metadata["robust_scale"], dtype=np.float64)

    @property
    def version(self) -> str:
        return self.metadata["baseline_version"]

    def _scaled(self, features: np.ndarray) -> np.ndarray:
        return (features - self._center) / self._scale

    def score(self, signal, sampling_frequency_hz: float, *, top_features: int = 3) -> dict:
        """Compare one window with this machine's normal.

        ``drift_score`` is the Isolation Forest anomaly score (higher is more
        unusual) and ``threshold`` was set from held-back healthy windows.
        """
        contract = self.metadata["input_contract"]
        required_frequency = float(contract["sampling_frequency_hz"])
        if not np.isclose(float(sampling_frequency_hz), required_frequency):
            raise ValueError(f"sampling frequency {sampling_frequency_hz} Hz does not match baseline requirement {required_frequency} Hz")
        values = validate_signal(signal, sampling_frequency_hz, minimum_samples=int(contract["window_samples"]))
        if len(values) != int(contract["window_samples"]):
            raise ValueError(f"signal window must contain exactly {contract['window_samples']} samples")
        deviations = self._scaled(feature_vector(values, sampling_frequency_hz))
        drift_score = float(-self.model.score_samples(deviations.reshape(1, -1))[0])
        threshold = float(self.metadata["threshold"])
        ranked = np.argsort(-np.abs(deviations))[:top_features]
        names = feature_names()
        return {
            "drift_score": drift_score,
            "threshold": threshold,
            "drift_ratio": drift_score / threshold if threshold > 0 else None,
            "drifted": drift_score > threshold,
            "changed_features": [
                {"feature": names[index], "deviation": float(deviations[index]),
                 "direction": "higher" if deviations[index] > 0 else "lower"}
                for index in ranked
            ],
            "baseline_version": self.version,
        }


def fit_healthy_baseline(windows, sampling_frequency_hz: float, *, asset_id: str, component_id: str = "bearing-drive-end",
                         false_alarm_rate: float = 0.01, trees: int = 200, seed: int = 42) -> HealthyBaseline:
    """Fit a baseline from windows of ordinary running, in recorded order.

    The last fifth of the windows is held back to set the alarm threshold, so
    the threshold reflects healthy data the forest has not seen.
    """
    windows = np.asarray(windows, dtype=np.float64)
    if windows.ndim != 2:
        raise ValueError("windows must be a two-dimensional array of equal-length vibration windows")
    if len(windows) < MINIMUM_HEALTHY_WINDOWS:
        raise ValueError(f"a healthy baseline needs at least {MINIMUM_HEALTHY_WINDOWS} windows; received {len(windows)}")
    if not 0 < false_alarm_rate < 0.5:
        raise ValueError("false_alarm_rate must be between 0 and 0.5")
    features = np.asarray([feature_vector(window, sampling_frequency_hz) for window in windows])
    held_back = max(len(features) // 5, 8)
    fit_features, calibration_features = features[:-held_back], features[-held_back:]
    center, scale = _robust_scale(fit_features)
    model = IsolationForest(n_estimators=trees, contamination="auto", random_state=seed, n_jobs=1)
    model.fit((fit_features - center) / scale)
    calibration_scores = -model.score_samples((calibration_features - center) / scale)
    threshold = float(np.quantile(calibration_scores, 1 - false_alarm_rate))
    metadata = {
        "bundle_schema_version": BASELINE_SCHEMA, "kind": BASELINE_KIND,
        "baseline_version": "axon-healthy-baseline-unsaved",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "asset_id": asset_id, "component_id": component_id,
        "preprocessing_version": FEATURE_VERSION,
        "input_contract": {"sensor_type": "vibration", "sampling_frequency_hz": float(sampling_frequency_hz),
                           "window_samples": int(windows.shape[1]), "feature_names": list(feature_names())},
        "robust_center": center.tolist(), "robust_scale": scale.tolist(),
        "threshold": threshold, "target_false_alarm_rate": false_alarm_rate,
        "healthy_windows": {"fit": int(len(fit_features)), "threshold_calibration": int(len(calibration_features))},
        "training": {"seed": seed, "trees": trees,
                     "library_versions": {"python": platform.python_version(), "scikit_learn": sklearn.__version__}},
    }
    return HealthyBaseline(model, metadata)


def save_healthy_baseline(baseline: HealthyBaseline, output_dir: Path) -> dict:
    output_dir = Path(output_dir); output_dir.mkdir(parents=True, exist_ok=True)
    model_path = output_dir / "baseline.joblib"
    joblib.dump(baseline.model, model_path)
    digest = _sha256(model_path)
    baseline.metadata["artifact"] = {"filename": model_path.name, "sha256": digest}
    baseline.metadata["baseline_version"] = f"axon-healthy-baseline-{digest[:12]}"
    (output_dir / "metadata.json").write_text(json.dumps(baseline.metadata, indent=2) + "\n", encoding="utf-8")
    return baseline.metadata


def load_healthy_baseline(baseline_dir: Path) -> HealthyBaseline:
    baseline_dir = Path(baseline_dir)
    try:
        metadata = json.loads((baseline_dir / "metadata.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HealthyBaselineError("healthy baseline metadata is missing or invalid") from exc
    if metadata.get("bundle_schema_version") != BASELINE_SCHEMA or metadata.get("kind") != BASELINE_KIND:
        raise HealthyBaselineError("unsupported healthy baseline schema")
    artifact = metadata.get("artifact", {}); model_path = baseline_dir / str(artifact.get("filename", ""))
    if not model_path.is_file() or _sha256(model_path) != artifact.get("sha256"):
        raise HealthyBaselineError("healthy baseline artifact is missing or checksum verification failed")
    contract = metadata.get("input_contract", {})
    if list(contract.get("feature_names", [])) != list(feature_names()):
        raise HealthyBaselineError("healthy baseline feature order does not match this runtime")
    if len(metadata.get("robust_center", [])) != len(feature_names()) or len(metadata.get("robust_scale", [])) != len(feature_names()):
        raise HealthyBaselineError("healthy baseline scaling does not match its feature contract")
    trained_version = metadata.get("training", {}).get("library_versions", {}).get("scikit_learn")
    if trained_version and trained_version != sklearn.__version__:
        raise HealthyBaselineError(f"baseline requires scikit-learn {trained_version}; installed {sklearn.__version__}. Install ml/requirements-bearing.txt")
    try:
        model = joblib.load(model_path)
    except Exception as exc:
        raise HealthyBaselineError("healthy baseline artifact cannot be loaded") from exc
    if not hasattr(model, "score_samples"):
        raise HealthyBaselineError("healthy baseline artifact is not an anomaly detector")
    return HealthyBaseline(model, metadata)


def evaluate_baseline(baseline: HealthyBaseline, signals: np.ndarray, labels: np.ndarray, groups: np.ndarray,
                      sampling_frequency_hz: float, *, exclude_group: str) -> dict:
    """Score every window from the other physical bearings in a prepared set."""
    per_group: dict[str, dict] = {}
    for group in sorted(set(groups.tolist()) - {exclude_group}):
        indices = np.flatnonzero(groups == group)
        flagged = sum(baseline.score(signals[index], sampling_frequency_hz)["drifted"] for index in indices)
        per_group[group] = {"label": str(labels[indices[0]]), "windows": int(len(indices)), "flagged": int(flagged)}
    healthy = [item for item in per_group.values() if item["label"] == "healthy"]
    damaged = [item for item in per_group.values() if item["label"] != "healthy"]
    rate = lambda items: (sum(item["flagged"] for item in items) / sum(item["windows"] for item in items)) if items else None
    return {
        "baseline_version": baseline.version, "fitted_on_group": exclude_group, "per_bearing": per_group,
        "other_healthy_bearings_flagged_rate": rate(healthy), "damaged_bearings_flagged_rate": rate(damaged),
        "warning": "A baseline is specific to one machine and mounting. Windows from other bearings show how the detector "
                   "behaves on this dataset only; flags on other healthy bearings are expected and are not field false alarms.",
    }


def main() -> None:
    from ml.bearing.training import load_prepared

    parser = argparse.ArgumentParser(description="Fit a healthy-only baseline for one machine from a prepared dataset.")
    parser.add_argument("--prepared", type=Path, required=True, help="Prepared .npz with signals, labels, groups, sampling_frequency_hz")
    parser.add_argument("--group", required=True, help="Physical bearing (group) whose healthy windows define normal")
    parser.add_argument("--asset-id", required=True)
    parser.add_argument("--component-id", default="bearing-drive-end")
    parser.add_argument("--output", type=Path, help="Defaults to ml/artifacts/bearing/baselines/<asset-id>")
    parser.add_argument("--false-alarm-rate", type=float, default=0.01)
    parser.add_argument("--evaluate", action="store_true", help="Also score all other bearings and write evaluation.json")
    args = parser.parse_args()
    signals, labels, groups, sampling_frequency = load_prepared(args.prepared)
    selected = groups == args.group
    if not selected.any():
        parser.error(f"group {args.group!r} is not in the prepared dataset")
    if set(labels[selected].tolist()) != {"healthy"}:
        parser.error(f"group {args.group!r} is not labelled healthy; a baseline must be fitted on normal running only")
    baseline = fit_healthy_baseline(signals[selected], sampling_frequency, asset_id=args.asset_id,
                                    component_id=args.component_id, false_alarm_rate=args.false_alarm_rate)
    output = args.output or Path(__file__).resolve().parents[2] / "ml" / "artifacts" / "bearing" / "baselines" / args.asset_id
    metadata = save_healthy_baseline(baseline, output)
    summary = {"baseline_version": metadata["baseline_version"], "output": str(output), "healthy_windows": metadata["healthy_windows"]}
    if args.evaluate:
        report = evaluate_baseline(baseline, signals, labels, groups, sampling_frequency, exclude_group=args.group)
        (output / "evaluation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        summary["evaluation"] = {key: report[key] for key in ("other_healthy_bearings_flagged_rate", "damaged_bearings_flagged_rate")}
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
