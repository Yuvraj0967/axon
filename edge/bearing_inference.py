"""Offline MQTT edge service for a validated Paderborn bearing bundle."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

import paho.mqtt.client as mqtt

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path: sys.path.insert(0, str(PROJECT_ROOT))

from edge.diagnostic_journal import BoundedDiagnosticJournal
from ml.bearing.bundle import BearingBundleError, load_bearing_bundle
from shared.diagnosis import diagnosis_from_probabilities, unavailable_diagnosis


def diagnose_payload(payload: dict, bundle=None, model_error: str | None = None) -> dict:
    asset_id, component_id = payload.get("asset_id", "unknown-asset"), payload.get("component_id", "unknown-component")
    if model_error: return unavailable_diagnosis(asset_id, component_id, model_error)
    try:
        probabilities = bundle.probabilities(payload["signal"], payload["sampling_frequency_hz"])
        return diagnosis_from_probabilities(asset_id, component_id, probabilities, bundle.metadata["model_version"], evidence=[{"kind": "vibration_window", "sampling_frequency_hz": payload["sampling_frequency_hz"], "samples": len(payload["signal"])}])
    except (KeyError, TypeError, ValueError) as exc:
        return unavailable_diagnosis(asset_id, component_id, str(exc), status="SENSOR_DATA_INVALID")


def main() -> None:
    broker, port = os.getenv("MQTT_HOST", os.getenv("BROKER_IP", "localhost")), int(os.getenv("MQTT_PORT", "1883"))
    artifact = Path(os.getenv("AXON_BEARING_MODEL_DIR", PROJECT_ROOT / "ml" / "artifacts" / "bearing" / "active"))
    journal = BoundedDiagnosticJournal(Path(os.getenv("AXON_DIAGNOSTIC_JOURNAL", PROJECT_ROOT / "edge" / "runtime" / "diagnostics.json")), int(os.getenv("AXON_DIAGNOSTIC_JOURNAL_LIMIT", "1000")))
    try: bundle, model_error = load_bearing_bundle(artifact), None
    except BearingBundleError as exc: bundle, model_error = None, str(exc)
    client = mqtt.Client()
    def on_message(client, userdata, message):
        try: payload = json.loads(message.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            print("ignored invalid bearing MQTT payload"); return
        diagnosis = diagnose_payload(payload, bundle, model_error)
        journal.append(diagnosis)
        client.publish(f"factory/{diagnosis['asset_id']}/diagnostic", json.dumps(diagnosis), qos=1)
    client.on_message = on_message; client.connect(broker, port, keepalive=30); client.subscribe("factory/+/bearing-vibration", qos=1); client.loop_forever()


if __name__ == "__main__": main()
