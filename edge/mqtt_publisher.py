"""Simulated plant gateway: publishes bearing evidence over MQTT.

There is no physical radio or accelerometer in this deployment, so this process
plays the role of the on-site gateway. It is honest about that: every event it
publishes carries ``simulated: true`` and names the historical recording it was
produced from, and the certificate that eventually uses the evidence repeats the
disclosure.

Real firmware replaces this file, not the topic contract::

    axon/v1/{org_id}/{site_id}/{device_id}/diagnostic
    axon/v1/{org_id}/{site_id}/{device_id}/window
    axon/v1/{org_id}/{site_id}/{device_id}/status

Example (plaintext, local broker)::

    python -m edge.mqtt_publisher --insecure --org org_x --site sit_y \\
        --device plant1-gw-01 --asset ast_z --component cmp_w \\
        --recording N09_M07_F10_KA04_1 --window 0 --mode diagnostic
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.ingest_service import address_for  # noqa: E402
from backend.paderborn_replay import (  # noqa: E402
    PaderbornReplayError,
    catalog as paderborn_catalog,
    read_window as read_paderborn_window,
)

log = logging.getLogger("axon.mqtt_publisher")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class GatewayPublisher:
    """Publishes evidence for one organisation, site and device."""

    def __init__(self, args, client_factory=None):
        self.args = args
        self.prefix = args.prefix
        self.client = self._build_client(client_factory)

    # --------------------------------------------------------------- client

    def _build_client(self, client_factory=None):
        if client_factory is not None:
            return client_factory()
        try:
            import paho.mqtt.client as mqtt
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise RuntimeError(
                "paho-mqtt is required: pip install paho-mqtt") from exc
        try:
            client = mqtt.Client(callback_api=mqtt.CallbackAPIVersion.VERSION2,
                                 client_id=f"{self.args.device}-publisher",
                                 protocol=mqtt.MQTTv311)
        except AttributeError:  # pragma: no cover - paho 1.x
            client = mqtt.Client(client_id=f"{self.args.device}-publisher",
                                 protocol=mqtt.MQTTv311)
        if self.args.username:
            client.username_pw_set(self.args.username, self.args.password)
        if not self.args.insecure:
            import ssl
            client.tls_set(ca_certs=self.args.ca, certfile=self.args.cert,
                           keyfile=self.args.key, tls_version=ssl.PROTOCOL_TLS_CLIENT)
            client.tls_insecure_set(False)
        return client

    def connect(self):
        self.client.connect(self.args.host, self.args.port, keepalive=60)
        self.client.loop_start()

    def close(self):
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except Exception:  # pragma: no cover - best effort
            pass

    # ------------------------------------------------------------- payloads

    def topic(self, kind: str) -> str:
        return address_for(self.args.org, self.args.site, self.args.device, kind,
                           self.prefix)

    def publish(self, kind: str, document: dict) -> str:
        topic = self.topic(kind)
        info = self.client.publish(topic, json.dumps(document),
                                   qos=self.args.qos, retain=False)
        info.wait_for_publish(timeout=10)
        log.info("published %s to %s", kind, topic)
        return topic

    def _evidence(self, recording_id: str, window_index: int) -> dict:
        record, signal, sampling_frequency = read_paderborn_window(
            recording_id, window_index)
        return {
            "record": record,
            "signal": signal,
            "sampling_frequency_hz": float(sampling_frequency),
        }

    def _status_payload(self) -> dict:
        return {
            "device_id": self.args.device,
            "site_id": self.args.site,
            "ts": utc_now(),
            "state": "online",
            "simulated": True,
            "note": "AXON Verify simulated plant gateway (no physical radio present)",
            "publishing": {"mode": self.args.mode, "interval_s": self.args.interval},
        }

    def _diagnostic_payload(self, evidence: dict) -> dict:
        from backend.ingestion import diagnose_signal

        record = evidence["record"]
        outcome = diagnose_signal(
            self.args.asset, self.args.component, evidence["signal"],
            evidence["sampling_frequency_hz"], source="mqtt", simulated=True,
            captured_at=utc_now(),
            evidence_extra=[{
                "kind": "vibration_window", "source": "paderborn_dataset_replay",
                "transport": "mqtt", "historical_replay": True,
                "recording_id": record["recording_id"], "bearing_id": record["bearing_id"],
                "operating_condition": record["operating_condition"],
                "documented_fault_class": record["fault_class"],
                "documented_fault_location": record["fault_location"],
                "damage_type": record["damage_type"], "label_source": record["label_source"],
                "license_id": record["license_id"],
            }])
        diagnostic = outcome.diagnostic
        return {
            "event_id": diagnostic["event_id"],
            "asset_id": self.args.asset,
            "component_id": self.args.component,
            "status": diagnostic["status"],
            "fault_class": diagnostic.get("fault_class"),
            "fault_location": diagnostic.get("fault_location"),
            "confidence": diagnostic.get("confidence"),
            "confidence_calibrated": bool(outcome.calibrated),
            "probabilities": diagnostic.get("probabilities") or {},
            "model_version": outcome.model_version,
            "calibration_version": outcome.calibration_version,
            "captured_at": diagnostic.get("timestamp") or utc_now(),
            "sampling_frequency_hz": evidence["sampling_frequency_hz"],
            "window_samples": int(len(evidence["signal"])),
            "operating_condition_id": record["operating_condition"],
            "simulated": True,
            "reading_sha256": None,
            "evidence": [{
                "kind": "vibration_window",
                "source": "paderborn_dataset_replay",
                "transport": "mqtt",
                "historical_replay": True,
                "recording_id": record["recording_id"],
                "bearing_id": record["bearing_id"],
                "license_id": record["license_id"],
            }],
        }

    def _window_payload(self, evidence: dict) -> dict:
        record = evidence["record"]
        return {
            "event_id": str(uuid4()),
            "asset_id": self.args.asset,
            "component_id": self.args.component,
            "sampling_frequency_hz": evidence["sampling_frequency_hz"],
            "operating_condition_id": record["operating_condition"],
            "captured_at": utc_now(),
            # Publish a compact float list; the backend scores it and stores the
            # full evidence record.
            "signal": [round(float(value), 6) for value in evidence["signal"].tolist()],
            "simulated": True,
            "provenance": {
                "source": "paderborn_dataset_replay",
                "recording_id": record["recording_id"],
                "bearing_id": record["bearing_id"],
                "license_id": record["license_id"],
            },
        }

    # --------------------------------------------------------------- run

    def run_once(self, recording_id: str, window_index: int) -> dict:
        if self.args.mode == "status":
            return {"topic": self.publish("status", self._status_payload()),
                    "kind": "status"}
        evidence = self._evidence(recording_id, window_index)
        if self.args.mode == "window":
            return {"topic": self.publish("window", self._window_payload(evidence)),
                    "kind": "window"}
        payload = self._diagnostic_payload(evidence)
        return {"topic": self.publish("diagnostic", payload), "kind": "diagnostic",
                "event_id": payload["event_id"], "status": payload["status"]}

    def run(self) -> None:
        catalog = paderborn_catalog()
        recordings = [(record["recording_id"], index)
                      for record in catalog.get("records", [])
                      for index in (0, 1)]
        if not recordings and self.args.mode != "status":
            raise SystemExit(
                "no packaged recordings are available; use --mode status or provide "
                "a recording via --recording")

        sequence = 0
        while True:
            if self.args.mode == "status":
                recording_id, window_index = None, None
            else:
                if self.args.recording:
                    recording_id, window_index = self.args.recording, self.args.window
                else:
                    recording_id, window_index = recordings[sequence % len(recordings)]
            try:
                result = self.run_once(recording_id, window_index)
                log.info("published %s", result)
            except PaderbornReplayError as exc:
                log.error("could not read %s[%s]: %s", recording_id, window_index, exc)
            sequence += 1
            if self.args.count and sequence >= self.args.count:
                break
            time.sleep(max(self.args.interval, 0.05))
        self.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m edge.mqtt_publisher",
        description="Simulated AXON Verify plant gateway (MQTT publisher).")
    parser.add_argument("--host", default=os.getenv("AXON_MQTT_HOST", "localhost"))
    parser.add_argument("--port", type=int,
                        default=int(os.getenv("AXON_MQTT_PORT", "1883")))
    parser.add_argument("--insecure", action="store_true",
                        help="plaintext MQTT for a local broker (never for production)")
    parser.add_argument("--ca", default=os.getenv("AXON_MQTT_CA"))
    parser.add_argument("--cert", default=os.getenv("AXON_MQTT_CERT"))
    parser.add_argument("--key", default=os.getenv("AXON_MQTT_KEY"))
    parser.add_argument("--username", default=os.getenv("AXON_MQTT_USERNAME"))
    parser.add_argument("--password", default=os.getenv("AXON_MQTT_PASSWORD"))
    parser.add_argument("--prefix", default=os.getenv("AXON_MQTT_TOPIC_PREFIX", "axon/v1"))
    parser.add_argument("--qos", type=int, default=1)

    parser.add_argument("--org", required=True, help="organisation id (tenant prefix)")
    parser.add_argument("--site", required=True, help="site id")
    parser.add_argument("--device", required=True, help="registered device key")
    parser.add_argument("--asset", required=True, help="asset id inside the tenant")
    parser.add_argument("--component", required=True, help="component id inside the asset")

    parser.add_argument("--mode", choices=("diagnostic", "window", "status"),
                        default="diagnostic")
    parser.add_argument("--recording", default=None,
                        help="packaged recording id; omit to cycle the catalogue")
    parser.add_argument("--window", type=int, default=0)
    parser.add_argument("--count", type=int, default=1,
                        help="number of events; 0 means run until interrupted")
    parser.add_argument("--interval", type=float, default=5.0)
    parser.add_argument("--log-level", default=os.getenv("LOG_LEVEL", "INFO"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=args.log_level,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    publisher = GatewayPublisher(args)
    publisher.connect()
    publisher.run()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
