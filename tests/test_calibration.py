"""Probability calibration: fit, apply, and honest reporting of absence."""
from __future__ import annotations

import json
import math

import pytest

from backend.calibration import (
    Calibration,
    CalibrationError,
    apply_temperature,
    calibrated_state,
    expected_calibration_error,
    fit_temperature_scaling,
    load_calibration,
    save_calibration,
)

CLASSES = ["healthy", "other_bearing_damage"]


def _rows(confidence: float, label: str, count: int) -> tuple[list[dict], list[str]]:
    """`count` rows that are all `confidence` sure of `label`."""
    other = 1.0 - confidence
    rows = []
    labels = []
    for _ in range(count):
        row = {"healthy": 0.0, "other_bearing_damage": 0.0}
        row[label] = confidence
        row[CLASSES[0] if label == CLASSES[1] else CLASSES[1]] = other
        rows.append(row)
        labels.append(label)
    return rows, labels


def _combine(*pairs: tuple[list[dict], list[str]]) -> tuple[list[dict], list[str]]:
    rows: list[dict] = []
    labels: list[str] = []
    for part_rows, part_labels in pairs:
        rows += part_rows
        labels += part_labels
    return rows, labels


def _calibration_dataset(correct_fraction: float, confidence: float,
                         count: int = 400) -> tuple[list[dict], list[str]]:
    """Rows reported at `confidence` where only `correct_fraction` are right.

    This is the shape real held-out data has: the model is not right as often as
    it is confident, which is exactly what calibration has to correct.
    """
    rows: list[dict] = []
    labels: list[str] = []
    correct_count = int(round(count * correct_fraction))
    for index in range(count):
        label = CLASSES[index % 2]
        is_correct = index < correct_count
        predicted = label if is_correct else CLASSES[1 - CLASSES.index(label)]
        if predicted == "healthy":
            rows.append({"healthy": confidence, "other_bearing_damage": 1.0 - confidence})
        else:
            rows.append({"healthy": 1.0 - confidence, "other_bearing_damage": confidence})
        labels.append(label)
    return rows, labels


def test_fitting_on_well_calibrated_data_keeps_temperature_near_one():
    rows, labels = _calibration_dataset(correct_fraction=0.9, confidence=0.9)
    calibration = fit_temperature_scaling(rows, labels, CLASSES, version="cal-test")
    assert calibration.version == "cal-test"
    assert 0.7 < calibration.temperature < 1.4
    assert calibration.metrics["ece_after"] <= calibration.metrics["ece_before"] + 1e-9


def test_fitting_softens_overconfident_scores():
    """Confident scores that are only right 70% of the time must be pulled down."""
    rows, labels = _calibration_dataset(correct_fraction=0.7, confidence=0.95)
    calibration = fit_temperature_scaling(rows, labels, CLASSES)
    assert calibration.temperature > 1.4, "overconfident scores should be softened"
    assert calibration.metrics["ece_after"] < calibration.metrics["ece_before"]
    scaled = apply_temperature({"healthy": 0.95, "other_bearing_damage": 0.05},
                               calibration.temperature, CLASSES)
    assert scaled["healthy"] < 0.95


def test_apply_temperature_normalises_and_preserves_the_winner():
    scaled = apply_temperature({"healthy": 0.9, "other_bearing_damage": 0.1}, 2.0, CLASSES)
    assert math.isclose(sum(scaled.values()), 1.0, rel_tol=1e-9)
    assert max(scaled, key=scaled.get) == "healthy"
    hotter = apply_temperature({"healthy": 0.9, "other_bearing_damage": 0.1}, 0.5, CLASSES)
    assert hotter["healthy"] > scaled["healthy"], "a lower temperature sharpens the score"


def test_temperature_must_be_positive():
    with pytest.raises(CalibrationError):
        apply_temperature({"healthy": 1.0}, 0.0, CLASSES)


def test_ece_is_zero_for_a_perfectly_calibrated_set():
    rows, labels = _combine(_rows(0.5, "healthy", 100), _rows(0.5, "other_bearing_damage", 100))
    assert expected_calibration_error(rows, labels, CLASSES) == pytest.approx(0.0, abs=1e-9)


def test_fitting_needs_paired_data():
    with pytest.raises(CalibrationError):
        fit_temperature_scaling([{"healthy": 1.0}], [], CLASSES)
    with pytest.raises(CalibrationError):
        fit_temperature_scaling([{"healthy": 1.0}], ["healthy", "healthy"], CLASSES)


def test_fitting_rejects_rows_that_do_not_cover_every_class():
    with pytest.raises(CalibrationError):
        fit_temperature_scaling([{"healthy": 1.0}], ["healthy"], CLASSES)


def test_artifact_round_trip(tmp_path):
    rows, labels = _combine(_rows(0.9, "healthy", 50), _rows(0.9, "other_bearing_damage", 50))
    calibration = fit_temperature_scaling(
        rows, labels, CLASSES, version="cal-2026-01",
        validation_set={"groups": ["K002", "KI14"], "windows": 100, "split": "held-out"})
    path = save_calibration(calibration, tmp_path / "calibration.json")
    loaded = load_calibration(path)
    assert loaded is not None
    assert loaded.version == "cal-2026-01"
    assert loaded.temperature == calibration.temperature
    assert loaded.validation_set["groups"] == ["K002", "KI14"]
    document = json.loads(path.read_text())
    assert document["calibration_schema"] == "axon-calibration-v1"


def test_missing_artifact_reports_none(tmp_path):
    assert load_calibration(tmp_path / "absent.json") is None


def test_corrupt_artifact_is_treated_as_absent_not_as_a_fitted_model(tmp_path):
    path = tmp_path / "calibration.json"
    path.write_text('{"calibration_schema": "axon-calibration-v1"}')
    assert load_calibration(path) is None
    path.write_text("not json at all")
    assert load_calibration(path) is None
    path.write_text(json.dumps({
        "calibration_schema": "axon-calibration-v1", "temperature": -1,
        "classes": ["healthy"]}))
    assert load_calibration(path) is None


def test_calibration_state_is_always_self_describing(monkeypatch, tmp_path):
    """Absence must be reported as absence, presence must carry its provenance."""
    monkeypatch.setenv("AXON_CALIBRATION_FILE", str(tmp_path / "absent.json"))
    state = calibrated_state()
    assert state["confidence_calibrated"] is False
    assert state["calibration_version"] is None
    assert "no calibration artifact" in state["reason"]

    rows, labels = _rows(0.9, "healthy", 50)
    path = save_calibration(
        fit_temperature_scaling(rows, labels, CLASSES, version="cal-x"),
        tmp_path / "present.json")
    monkeypatch.setenv("AXON_CALIBRATION_FILE", str(path))
    state = calibrated_state()
    assert state["confidence_calibrated"] is True
    assert state["calibration_version"] == "cal-x"
    assert "windows" in state["validation_set"] or state["validation_set"] == {}


def test_calibration_class_rejects_a_foreign_schema():
    with pytest.raises(CalibrationError):
        Calibration.from_dict({"calibration_schema": "other", "temperature": 1.0,
                               "classes": ["healthy"]})
