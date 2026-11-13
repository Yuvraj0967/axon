import json
from pathlib import Path

import numpy as np
import pytest

from edge.bearing_inference import diagnose_payload
from ml.bearing.baseline import (HealthyBaselineError, MINIMUM_HEALTHY_WINDOWS, evaluate_baseline,
                                 fit_healthy_baseline, load_healthy_baseline, save_healthy_baseline)
from shared.lora_protocol import decode_diagnostic, encode_diagnostic, gateway_diagnostic

ROOT = Path(__file__).resolve().parents[1]
RATE, SAMPLES = 1024.0, 256


def _healthy(rng, count):
    time = np.arange(SAMPLES) / RATE
    return np.asarray([np.sin(2 * np.pi * 50 * time + rng.uniform(0, 6.28)) + rng.normal(0, 0.05, SAMPLES) for _ in range(count)])


def _damaged(rng, count):
    windows = _healthy(rng, count)
    windows[:, ::32] += 6.0  # periodic impacts, as a damaged race produces
    return windows


def _baseline(rng):
    return fit_healthy_baseline(_healthy(rng, 200), RATE, asset_id="loom-3")


def test_baseline_learns_normal_without_fault_labels_and_flags_drift():
    rng = np.random.default_rng(7)
    baseline = _baseline(rng)
    healthy_flags = [baseline.score(window, RATE)["drifted"] for window in _healthy(rng, 100)]
    damaged = [baseline.score(window, RATE) for window in _damaged(rng, 100)]
    assert sum(healthy_flags) <= 10
    assert all(result["drifted"] for result in damaged)
    assert damaged[0]["drift_ratio"] > 1 and len(damaged[0]["changed_features"]) == 3
    assert {"feature", "deviation", "direction"} <= set(damaged[0]["changed_features"][0])


def test_baseline_refuses_too_little_healthy_running():
    rng = np.random.default_rng(1)
    with pytest.raises(ValueError, match="at least"):
        fit_healthy_baseline(_healthy(rng, MINIMUM_HEALTHY_WINDOWS - 1), RATE, asset_id="loom-3")


def test_baseline_round_trip_checks_integrity_and_input_contract():
    rng = np.random.default_rng(3)
    output = ROOT / "test-results" / "healthy-baseline-test"
    metadata = save_healthy_baseline(_baseline(rng), output)
    loaded = load_healthy_baseline(output)
    assert loaded.version == metadata["baseline_version"] and loaded.version.startswith("axon-healthy-baseline-")
    assert loaded.score(_damaged(rng, 1)[0], RATE)["drifted"]
    with pytest.raises(ValueError, match="sampling frequency"):
        loaded.score(np.zeros(SAMPLES), RATE * 2)
    with pytest.raises(ValueError, match="exactly"):
        loaded.score(np.zeros(SAMPLES * 2), RATE)
    tampered = json.loads((output / "metadata.json").read_text(encoding="utf-8"))
    tampered["artifact"]["sha256"] = "0" * 64
    (output / "metadata.json").write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(HealthyBaselineError, match="checksum"):
        load_healthy_baseline(output)


def test_baseline_evaluation_reports_other_bearings_separately():
    rng = np.random.default_rng(5)
    baseline = _baseline(rng)
    signals = np.concatenate([_healthy(rng, 20), _healthy(rng, 20), _damaged(rng, 20)])
    labels = np.asarray(["healthy"] * 40 + ["other_bearing_damage"] * 20)
    groups = np.asarray(["K001"] * 20 + ["K002"] * 20 + ["KA04"] * 20)
    report = evaluate_baseline(baseline, signals, labels, groups, RATE, exclude_group="K001")
    assert set(report["per_bearing"]) == {"K002", "KA04"}
    assert report["damaged_bearings_flagged_rate"] == 1.0 and report["other_healthy_bearings_flagged_rate"] <= 0.25


def test_edge_uses_baseline_as_primary_detector_and_result_survives_lora():
    rng = np.random.default_rng(11)
    baseline = _baseline(rng)
    payload = {"asset_id": "loom-3", "component_id": "bearing-drive-end", "signal": _damaged(rng, 1)[0], "sampling_frequency_hz": RATE}
    drifted = diagnose_payload(payload, bundle=None, baseline=baseline)
    assert drifted["status"] == "FAULT_SUSPECTED" and drifted["fault_class"] == "unknown" and drifted["confidence"] is None
    assert drifted["evidence"][0]["detector"] == "healthy_only_baseline" and drifted["requires_technician_confirmation"]
    normal = diagnose_payload(payload | {"signal": _healthy(rng, 1)[0]}, bundle=None, baseline=baseline)
    assert normal["status"] == "HEALTHY_WITHIN_VALIDATED_SCOPE" and normal["fault_class"] == "healthy"
    received = gateway_diagnostic(decode_diagnostic(encode_diagnostic(drifted, 1)))
    assert received["status"] == "FAULT_SUSPECTED" and received["model_version"] == baseline.version
    invalid = diagnose_payload(payload | {"sampling_frequency_hz": RATE * 2}, bundle=None, baseline=baseline)
    assert invalid["status"] == "SENSOR_DATA_INVALID"
