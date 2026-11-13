"""Safety-oriented conversion from model probabilities to diagnostic records."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from ml.bearing.taxonomy import FAULTS

DIAGNOSTIC_STATUSES = {"HEALTHY_WITHIN_VALIDATED_SCOPE", "FAULT_SUSPECTED", "DIAGNOSIS_UNCERTAIN", "INSUFFICIENT_EVIDENCE", "OUT_OF_DISTRIBUTION", "UNSUPPORTED_FAULT", "SENSOR_DATA_INVALID", "MODEL_UNAVAILABLE", "AWAITING_TECHNICIAN_CONFIRMATION", "FAULT_CONFIRMED"}


def unavailable_diagnosis(asset_id: str, component_id: str, reason: str, *, status: str = "MODEL_UNAVAILABLE") -> dict:
    if status not in DIAGNOSTIC_STATUSES: raise ValueError("invalid diagnostic status")
    return {"event_id": str(uuid4()), "timestamp": datetime.now(timezone.utc).isoformat(), "asset_id": asset_id, "component_id": component_id, "fault_class": None, "fault_location": None, "confidence": None, "confidence_calibrated": False, "status": status, "evidence": [], "alternative_hypotheses": [], "missing_information": [reason], "recommended_confirmation_tests": [], "repair_reference_ids": [], "cost_estimate_id": None, "model_version": None, "requires_technician_confirmation": True, "simulated": False}


def diagnosis_from_probabilities(asset_id: str, component_id: str, probabilities: dict[str, float], model_version: str, *, minimum_probability: float = 0.70, evidence: list[dict] | None = None) -> dict:
    if not probabilities: return unavailable_diagnosis(asset_id, component_id, "model returned no class probabilities")
    ranked = sorted(probabilities.items(), key=lambda pair: pair[1], reverse=True)
    fault_class, confidence = ranked[0]
    if fault_class not in FAULTS:
        return unavailable_diagnosis(asset_id, component_id, f"unsupported model class: {fault_class}", status="UNSUPPORTED_FAULT")
    location = FAULTS[fault_class].fault_location
    if confidence < minimum_probability:
        status = "DIAGNOSIS_UNCERTAIN"
    elif fault_class == "healthy":
        status = "HEALTHY_WITHIN_VALIDATED_SCOPE"
    else:
        status = "FAULT_SUSPECTED"
    alternatives = [{"fault_class": label, "fault_location": FAULTS[label].fault_location if label in FAULTS else None, "score": score, "score_kind": "uncalibrated_classifier_probability"} for label, score in ranked[1:3]]
    return {"event_id": str(uuid4()), "timestamp": datetime.now(timezone.utc).isoformat(), "asset_id": asset_id, "component_id": component_id, "fault_class": fault_class, "fault_location": location, "confidence": confidence, "confidence_calibrated": False, "status": status, "evidence": evidence or [], "alternative_hypotheses": alternatives, "missing_information": ["Probability calibration and physical inspection are required before confirmation."], "recommended_confirmation_tests": ["Perform inspection according to equipment-specific authorized documentation."], "repair_reference_ids": [], "cost_estimate_id": None, "model_version": model_version, "requires_technician_confirmation": status != "HEALTHY_WITHIN_VALIDATED_SCOPE", "simulated": False}


def diagnosis_from_baseline(asset_id: str, component_id: str, baseline_result: dict, *, classifier_probabilities: dict[str, float] | None = None, classifier_version: str | None = None, evidence: list[dict] | None = None) -> dict:
    """Build a diagnostic record with the healthy-only baseline as the detector.

    The baseline decides whether this window differs from the machine's own
    normal. It cannot name a fault, so a supervised classifier, when one is
    deployed, only contributes a secondary hint about the kind of damage.
    """
    drifted = bool(baseline_result["drifted"])
    hint = None
    if classifier_probabilities:
        label, score = max(classifier_probabilities.items(), key=lambda pair: pair[1])
        if label in FAULTS:
            hint = {"fault_class": label, "fault_location": FAULTS[label].fault_location, "score": score, "score_kind": "uncalibrated_classifier_probability", "model_version": classifier_version, "role": "secondary_hint"}
    if drifted:
        named = hint if hint and hint["fault_class"] not in {"healthy", "unknown"} else None
        fault_class, location = (named["fault_class"], named["fault_location"]) if named else ("unknown", None)
        status = "FAULT_SUSPECTED"
    else:
        fault_class, location, status = "healthy", None, "HEALTHY_WITHIN_VALIDATED_SCOPE"
    detector = {"kind": "healthy_baseline_comparison", "detector": "healthy_only_baseline", "baseline_version": baseline_result["baseline_version"], "drift_score": baseline_result["drift_score"], "threshold": baseline_result["threshold"], "drift_ratio": baseline_result.get("drift_ratio"), "changed_features": baseline_result.get("changed_features", [])}
    return {"event_id": str(uuid4()), "timestamp": datetime.now(timezone.utc).isoformat(), "asset_id": asset_id, "component_id": component_id, "fault_class": fault_class, "fault_location": location, "confidence": None, "confidence_calibrated": False, "status": status, "evidence": [detector] + list(evidence or []), "alternative_hypotheses": [hint] if hint else [], "missing_information": ["The baseline reports a change from this machine's normal running, not a confirmed fault. Physical inspection is required."] if drifted else [], "recommended_confirmation_tests": ["Perform inspection according to equipment-specific authorized documentation."] if drifted else [], "repair_reference_ids": [], "cost_estimate_id": None, "model_version": baseline_result["baseline_version"], "requires_technician_confirmation": drifted, "simulated": False}
