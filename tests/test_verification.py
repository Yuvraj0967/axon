"""Repair verification policy: deterministic verdicts from evidence alone."""
from __future__ import annotations

import pytest

from backend.verification import (
    CANNOT_VERIFY,
    INCONCLUSIVE,
    NOT_APPLICABLE,
    NOT_VERIFIED,
    VERIFIED,
    comparability,
    default_policy,
    verify_repair,
)

CALIBRATED = default_policy(calibrated=True)
UNCALIBRATED = default_policy(calibrated=False)

BASE = {
    "event_id": "event-before",
    "asset_id": "asset-1",
    "component_id": "cmp-1",
    "status": "FAULT_SUSPECTED",
    "fault_class": "other_bearing_damage",
    "confidence": 0.98,
    "confidence_calibrated": True,
    "probabilities": {"healthy": 0.02, "other_bearing_damage": 0.98},
    "model_version": "axon-bearing-rf-test",
    "captured_at": "2026-01-01T00:00:00+00:00",
    "sampling_frequency_hz": 64000.0,
    "window_samples": 4096,
    "operating_condition_id": "N09_M07_F10",
    "source": "upload",
    "simulated": False,
}


def after(**overrides) -> dict:
    record = dict(BASE) | {
        "event_id": "event-after",
        "status": "HEALTHY_WITHIN_VALIDATED_SCOPE",
        "fault_class": "healthy",
        "confidence": 0.99,
        "probabilities": {"healthy": 0.99, "other_bearing_damage": 0.01},
        "captured_at": "2026-01-02T00:00:00+00:00",
    }
    record.update(overrides)
    return record


def before(**overrides) -> dict:
    record = dict(BASE)
    record.update(overrides)
    return record


def codes(result: dict) -> list[str]:
    return [reason["code"] for reason in result["reasons"]]


# ------------------------------------------------------------------ happy path


def test_verified_when_fault_clears_with_margin():
    result = verify_repair(before(), after(), CALIBRATED)
    assert result["verdict"] == VERIFIED
    assert result["comparability"]["comparable"] is True
    assert "AFTER_HEALTHY" in codes(result)
    assert result["policy"]["policy_version"] == "axv-policy-v1"


def test_not_verified_when_fault_remains():
    result = verify_repair(before(), after(status="FAULT_SUSPECTED", fault_class="other_bearing_damage",
                                           probabilities={"healthy": 0.01, "other_bearing_damage": 0.99}),
                           CALIBRATED)
    assert result["verdict"] == NOT_VERIFIED
    assert "AFTER_STILL_FAULT" in codes(result)


def test_not_verified_notes_no_material_change():
    result = verify_repair(
        before(),
        after(status="FAULT_SUSPECTED", fault_class="other_bearing_damage",
              probabilities={"healthy": 0.02, "other_bearing_damage": 0.98}),
        CALIBRATED)
    assert result["verdict"] == NOT_VERIFIED
    assert "NO_CHANGE" in codes(result)


# --------------------------------------------------------------- refusal paths


def test_inconclusive_when_after_is_uncertain():
    result = verify_repair(before(), after(status="DIAGNOSIS_UNCERTAIN", confidence=0.55,
                                           probabilities={"healthy": 0.55, "other_bearing_damage": 0.45}),
                           CALIBRATED)
    assert result["verdict"] == INCONCLUSIVE
    assert codes(result) == ["AFTER_UNCERTAIN"]


def test_inconclusive_when_before_baseline_is_uncertain():
    result = verify_repair(before(status="DIAGNOSIS_UNCERTAIN", confidence=0.55), after(),
                           CALIBRATED)
    assert result["verdict"] == INCONCLUSIVE
    assert codes(result) == ["BEFORE_UNCERTAIN"]


def test_not_applicable_when_before_was_already_healthy():
    result = verify_repair(
        before(status="HEALTHY_WITHIN_VALIDATED_SCOPE", fault_class="healthy",
               probabilities={"healthy": 0.99, "other_bearing_damage": 0.01}),
        after(), CALIBRATED)
    assert result["verdict"] == NOT_APPLICABLE
    assert codes(result) == ["BEFORE_HEALTHY"]


def test_cannot_verify_when_model_is_unavailable():
    result = verify_repair(
        before(status="MODEL_UNAVAILABLE", confidence=None, model_version=None),
        after(status="MODEL_UNAVAILABLE", confidence=None, model_version=None),
        CALIBRATED)
    assert result["verdict"] == CANNOT_VERIFY
    assert "MODEL_UNAVAILABLE" in codes(result)


def test_cannot_verify_outranks_a_comparability_failure():
    """An unavailable model is a stronger statement than 'these records differ'."""
    result = verify_repair(
        before(status="MODEL_UNAVAILABLE", model_version=None, asset_id="asset-1"),
        after(status="MODEL_UNAVAILABLE", model_version=None, asset_id="asset-2"),
        CALIBRATED)
    assert result["verdict"] == CANNOT_VERIFY
    assert "MODEL_UNAVAILABLE" in codes(result)


def test_cannot_verify_when_sensor_data_is_invalid():
    result = verify_repair(before(), after(status="SENSOR_DATA_INVALID", confidence=None),
                           CALIBRATED)
    assert result["verdict"] == CANNOT_VERIFY
    assert "SENSOR_INVALID" in codes(result)


# --------------------------------------------------------------- comparability


def test_non_comparable_across_assets():
    result = verify_repair(before(), after(asset_id="asset-2"), CALIBRATED)
    assert result["verdict"] == INCONCLUSIVE
    assert "ASSET_MISMATCH" in codes(result)


def test_non_comparable_when_sampling_rate_is_missing_on_both_sides():
    result = verify_repair(before(sampling_frequency_hz=None), after(sampling_frequency_hz=None),
                           CALIBRATED)
    assert result["verdict"] == INCONCLUSIVE
    assert "NON_COMPARABLE" in codes(result)


def test_non_comparable_when_window_lengths_differ():
    result = verify_repair(before(), after(window_samples=2048), CALIBRATED)
    assert result["verdict"] == INCONCLUSIVE
    assert "NON_COMPARABLE" in codes(result)


def test_non_comparable_across_model_versions():
    result = verify_repair(before(), after(model_version="axon-bearing-rf-other"), CALIBRATED)
    assert result["verdict"] == INCONCLUSIVE
    assert "MODEL_MISMATCH" in codes(result)


def test_non_comparable_when_operating_conditions_differ():
    result = verify_repair(before(), after(operating_condition_id="N15_M07_F10"), CALIBRATED)
    assert result["verdict"] == INCONCLUSIVE
    assert "OPERATING_CONDITION_MISMATCH" in codes(result)


def test_non_comparable_when_one_side_records_no_operating_condition():
    result = verify_repair(before(), after(operating_condition_id=None), CALIBRATED)
    assert result["verdict"] == INCONCLUSIVE
    assert "OPERATING_CONDITION_MISMATCH" in codes(result)


def test_reversed_capture_order_blocks_verification():
    result = verify_repair(before(), after(captured_at="2025-12-31T00:00:00+00:00"),
                           CALIBRATED)
    assert result["verdict"] == INCONCLUSIVE
    assert "TIMESTAMP_ORDER" in codes(result)


def test_simultaneous_lab_captures_are_not_treated_as_a_reversal():
    result = verify_repair(before(), after(captured_at=BASE["captured_at"]), CALIBRATED)
    assert result["verdict"] == VERIFIED


def test_same_event_twice_is_not_a_repair():
    result = verify_repair(before(), after(event_id=BASE["event_id"]), CALIBRATED)
    assert result["verdict"] == INCONCLUSIVE
    assert "NO_CHANGE" in codes(result)


# ------------------------------------------------------------------ thresholds


def test_improvement_below_the_margin_is_inconclusive():
    """A device may report a confident class whose probabilities barely moved.

    The policy refuses: confidence alone is not evidence of repair.
    """
    result = verify_repair(
        before(probabilities={"healthy": 0.25, "other_bearing_damage": 0.75}, confidence=0.95),
        after(probabilities={"healthy": 0.52, "other_bearing_damage": 0.48}, confidence=0.9),
        CALIBRATED)
    assert result["verdict"] == INCONCLUSIVE
    assert "POLICY_MARGIN" in codes(result)


def test_residual_fault_probability_above_the_maximum_is_inconclusive():
    result = verify_repair(
        before(probabilities={"healthy": 0.2, "other_bearing_damage": 0.8}, confidence=0.9),
        after(probabilities={"healthy": 0.55, "other_bearing_damage": 0.45}, confidence=0.9),
        CALIBRATED)
    assert result["verdict"] == INCONCLUSIVE
    assert "POLICY_MARGIN" not in codes(result)
    assert "AFTER_DAMAGE_PROBABILITY" in codes(result)


def test_uncalibrated_policy_is_stricter_than_the_calibrated_one():
    assert UNCALIBRATED.minimum_after_confidence > CALIBRATED.minimum_after_confidence
    assert UNCALIBRATED.minimum_damage_drop > CALIBRATED.minimum_damage_drop
    assert UNCALIBRATED.maximum_after_damage_probability < CALIBRATED.maximum_after_damage_probability
    assert UNCALIBRATED.calibrated is False and any(UNCALIBRATED.warnings)


def test_uncalibrated_policy_refuses_a_marginal_case_that_calibrated_policy_accepts():
    marginal_before = before(probabilities={"healthy": 0.2, "other_bearing_damage": 0.8},
                             confidence=0.8)
    marginal_after = after(probabilities={"healthy": 0.75, "other_bearing_damage": 0.25},
                           confidence=0.75)
    assert verify_repair(marginal_before, marginal_after, CALIBRATED)["verdict"] == VERIFIED
    result = verify_repair(marginal_before, marginal_after, UNCALIBRATED)
    assert result["verdict"] == INCONCLUSIVE
    assert "AFTER_UNCERTAIN" in codes(result)
    assert result["policy"]["confidence_calibrated"] is False


def test_policy_is_deterministic():
    first = verify_repair(before(), after(), CALIBRATED)
    second = verify_repair(before(), after(), CALIBRATED)
    assert first == second


def test_verdict_is_never_an_invented_class():
    """The policy can only refuse, never confirm an unsupported claim."""
    for status in ("INSUFFICIENT_EVIDENCE", "OUT_OF_DISTRIBUTION", "UNSUPPORTED_FAULT"):
        result = verify_repair(before(), after(status=status), CALIBRATED)
        assert result["verdict"] in (INCONCLUSIVE, NOT_VERIFIED), status


# ----------------------------------------------------------------- comparability


def test_comparability_reports_every_failed_check():
    checks = comparability(
        before(asset_id=None), after(asset_id="asset-2", sampling_frequency_hz=None))
    assert checks["comparable"] is False
    assert checks["same_asset"] is False
    assert checks["same_sampling_rate"] is False


@pytest.mark.parametrize("missing", ["asset_id", "component_id"])
def test_missing_identity_never_counts_as_a_match(missing):
    checks = comparability(before(**{missing: None}), after(**{missing: None}))
    key = "same_asset" if missing == "asset_id" else "same_component"
    assert checks[key] is False
