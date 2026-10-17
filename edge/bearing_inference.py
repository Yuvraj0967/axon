"""Local Raspberry Pi bearing inference used before sending a LoRa summary."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path: sys.path.insert(0, str(PROJECT_ROOT))

from ml.bearing.bundle import BearingBundleError, load_bearing_bundle
from shared.diagnosis import diagnosis_from_probabilities, unavailable_diagnosis


def diagnose_payload(payload: dict, bundle=None, model_error: str | None = None) -> dict:
    asset_id, component_id = payload.get("asset_id", "unknown-asset"), payload.get("component_id", "unknown-component")
    if model_error: return unavailable_diagnosis(asset_id, component_id, model_error)
    try:
        probabilities = bundle.probabilities(payload["signal"], payload["sampling_frequency_hz"])
        return diagnosis_from_probabilities(asset_id, component_id, probabilities, bundle.metadata["model_version"], evidence=[{"kind": "vibration_window", "source": "raspberry_pi_local", "transport": "local_spi_adc", "sampling_frequency_hz": payload["sampling_frequency_hz"], "samples": len(payload["signal"])}])
    except (KeyError, TypeError, ValueError) as exc:
        return unavailable_diagnosis(asset_id, component_id, str(exc), status="SENSOR_DATA_INVALID")
