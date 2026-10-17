"""Axon FastAPI backend: validated MQTT ingest, storage, and command API."""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from functools import lru_cache
import json, logging, os
from pathlib import Path
import sys
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
import paho.mqtt.client as mqtt
import psycopg2
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")
from shared.health import compute_health
from shared.diagnosis import diagnosis_from_probabilities, unavailable_diagnosis
from ml.bearing.bundle import BearingBundleError, load_bearing_bundle
from ml.bearing.taxonomy import public_taxonomy
from backend.costs import estimate_cost
from backend.knowledge import search_documents

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("axon.backend")


class Telemetry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    machine_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    ts: datetime
    temp: float
    vibration: float
    current: float

    @field_validator("temp", "vibration", "current")
    @classmethod
    def finite(cls, value):
        if not -1_000_000 < value < 1_000_000:
            raise ValueError("sensor value is out of range")
        return value


class Alert(BaseModel):
    model_config = ConfigDict(extra="forbid")
    machine_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    ts: datetime
    type: str = Field(min_length=1, max_length=64)
    score: float


class DiagnosticEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str = Field(min_length=1, max_length=64)
    timestamp: datetime
    asset_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    component_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    fault_class: str | None = Field(default=None, max_length=64)
    fault_location: str | None = Field(default=None, max_length=64)
    confidence: float | None = None
    confidence_calibrated: bool
    status: str = Field(min_length=1, max_length=64)
    evidence: list[dict] = Field(default_factory=list)
    alternative_hypotheses: list[dict] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    recommended_confirmation_tests: list[str] = Field(default_factory=list)
    repair_reference_ids: list[str] = Field(default_factory=list)
    cost_estimate_id: str | None = None
    model_version: str | None = None
    requires_technician_confirmation: bool
    simulated: bool


class Command(BaseModel):
    model_config = ConfigDict(extra="forbid")
    machine_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    action: Literal["slow_down", "shutdown", "resume"]
    issued_by: str = Field(default="operator", min_length=1, max_length=64)


class DiagnosticRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    asset_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    component_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    signal: list[float] = Field(min_length=16, max_length=262_144)
    sampling_frequency_hz: float = Field(gt=0, le=1_000_000)


class CostEstimateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    line_items: list[dict] = Field(default_factory=list, max_length=100)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    tax_rate: float | None = Field(default=None, ge=0, le=1)
    labour_hours: float | None = Field(default=None, ge=0)
    labour_rate: float | None = Field(default=None, ge=0)


class TechnicianConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str = Field(min_length=1, max_length=64)
    technician_id: str = Field(min_length=1, max_length=128)
    decision: Literal["confirmed", "rejected", "inspection_recorded", "repair_outcome_recorded"]
    confirmed_fault_class: str | None = Field(default=None, max_length=64)
    notes: str | None = Field(default=None, max_length=2_000)


class MemoryStore:
    """Bounded storage for tests and explicit local development mode."""
    def __init__(self):
        self.readings_by_machine, self.alerts_by_machine, self.commands_by_machine = {}, {}, {}
        self.diagnostics_by_asset, self.technician_feedback = {}, []

    def write_telemetry(self, reading):
        values = self.readings_by_machine.setdefault(reading.machine_id, [])
        values.append(reading.model_dump(mode="json")); del values[:-10_000]

    def write_alert(self, alert):
        values = self.alerts_by_machine.setdefault(alert.machine_id, [])
        values.append(alert.model_dump(mode="json")); del values[:-1_000]

    def write_command(self, command, delivery_status):
        values = self.commands_by_machine.setdefault(command.machine_id, [])
        item = command.model_dump() | {"created": datetime.now(timezone.utc).isoformat(), "delivery_status": delivery_status}
        values.append(item); del values[:-1_000]

    def machines(self):
        return sorted(set(self.readings_by_machine) | set(self.alerts_by_machine) | set(self.commands_by_machine))

    def readings(self, machine_id, minutes):
        cutoff = datetime.now(timezone.utc).timestamp() - minutes * 60
        return [r for r in self.readings_by_machine.get(machine_id, []) if datetime.fromisoformat(r["ts"]).timestamp() >= cutoff]

    def alerts(self, machine_id): return list(reversed(self.alerts_by_machine.get(machine_id, [])[-50:]))
    def commands(self, machine_id): return list(reversed(self.commands_by_machine.get(machine_id, [])[-20:]))

    def write_diagnostic(self, diagnostic):
        values = self.diagnostics_by_asset.setdefault(diagnostic["asset_id"], [])
        values.append(diagnostic); del values[:-1_000]

    def diagnostics(self, asset_id, limit=50): return list(reversed(self.diagnostics_by_asset.get(asset_id, [])[-limit:]))
    def write_feedback(self, feedback): self.technician_feedback.append(feedback); del self.technician_feedback[:-1_000]


class ExternalStore:
    """InfluxDB telemetry and PostgreSQL alert/command persistence for Docker mode."""
    def __init__(self):
        self.bucket, self.org = os.getenv("INFLUX_BUCKET", "telemetry"), os.getenv("INFLUX_ORG", "axon")
        self.influx = InfluxDBClient(url=os.getenv("INFLUX_URL", "http://localhost:8086"), token=os.environ["INFLUX_TOKEN"], org=self.org)
        self.write_api, self.query_api = self.influx.write_api(write_options=SYNCHRONOUS), self.influx.query_api()
        self.pg = psycopg2.connect(host=os.getenv("POSTGRES_HOST", "localhost"), port=int(os.getenv("POSTGRES_PORT", "5432")), dbname=os.getenv("POSTGRES_DB", "axon"), user=os.getenv("POSTGRES_USER", "axon"), password=os.environ["POSTGRES_PASSWORD"])
        self.pg.autocommit = True
        with self.pg.cursor() as cur:
            cur.execute("CREATE TABLE IF NOT EXISTS alerts (id SERIAL PRIMARY KEY, machine_id TEXT, ts TIMESTAMPTZ, type TEXT, score DOUBLE PRECISION)")
            cur.execute("CREATE TABLE IF NOT EXISTS commands (id SERIAL PRIMARY KEY, machine_id TEXT, action TEXT, issued_by TEXT, created TIMESTAMPTZ DEFAULT now(), delivery_status TEXT)")
            cur.execute("CREATE TABLE IF NOT EXISTS diagnostic_events (id SERIAL PRIMARY KEY, event_id TEXT UNIQUE, asset_id TEXT, created TIMESTAMPTZ DEFAULT now(), payload JSONB NOT NULL)")
            cur.execute("CREATE TABLE IF NOT EXISTS technician_feedback (id SERIAL PRIMARY KEY, event_id TEXT, created TIMESTAMPTZ DEFAULT now(), payload JSONB NOT NULL)")

    def write_telemetry(self, reading):
        point = Point("telemetry").tag("machine_id", reading.machine_id).field("temp", reading.temp).field("vibration", reading.vibration).field("current", reading.current).time(reading.ts)
        self.write_api.write(bucket=self.bucket, record=point)

    def write_alert(self, alert):
        with self.pg.cursor() as cur: cur.execute("INSERT INTO alerts (machine_id, ts, type, score) VALUES (%s,%s,%s,%s)", (alert.machine_id, alert.ts, alert.type, alert.score))

    def write_command(self, command, delivery_status):
        with self.pg.cursor() as cur: cur.execute("INSERT INTO commands (machine_id, action, issued_by, delivery_status) VALUES (%s,%s,%s,%s)", (command.machine_id, command.action, command.issued_by, delivery_status))

    def machines(self): return ["M1"]

    def readings(self, machine_id, minutes):
        query = f'''from(bucket: "{self.bucket}") |> range(start: -{minutes}m) |> filter(fn: (r) => r._measurement == "telemetry" and r.machine_id == "{machine_id}") |> pivot(rowKey:["_time"], columnKey:["_field"], valueColumn:"_value")'''
        rows = []
        for table in self.query_api.query(query):
            for record in table.records: rows.append({"ts": record.get_time().isoformat(), "temp": record.values.get("temp"), "vibration": record.values.get("vibration"), "current": record.values.get("current")})
        return sorted(rows, key=lambda row: row["ts"])

    def alerts(self, machine_id):
        with self.pg.cursor() as cur:
            cur.execute("SELECT machine_id, ts, type, score FROM alerts WHERE machine_id=%s ORDER BY id DESC LIMIT 50", (machine_id,))
            return [{"machine_id":a, "ts":b.isoformat(), "type":c, "score":d} for a,b,c,d in cur.fetchall()]

    def commands(self, machine_id):
        with self.pg.cursor() as cur:
            cur.execute("SELECT machine_id, action, issued_by, created, delivery_status FROM commands WHERE machine_id=%s ORDER BY id DESC LIMIT 20", (machine_id,))
            return [{"machine_id":a, "action":b, "issued_by":c, "created":d.isoformat(), "delivery_status":e} for a,b,c,d,e in cur.fetchall()]

    def write_diagnostic(self, diagnostic):
        with self.pg.cursor() as cur: cur.execute("INSERT INTO diagnostic_events (event_id, asset_id, payload) VALUES (%s,%s,%s)", (diagnostic["event_id"], diagnostic["asset_id"], json.dumps(diagnostic)))

    def diagnostics(self, asset_id, limit=50):
        with self.pg.cursor() as cur:
            cur.execute("SELECT payload FROM diagnostic_events WHERE asset_id=%s ORDER BY id DESC LIMIT %s", (asset_id, limit))
            return [item[0] for item in cur.fetchall()]

    def write_feedback(self, feedback):
        with self.pg.cursor() as cur: cur.execute("INSERT INTO technician_feedback (event_id, payload) VALUES (%s,%s)", (feedback["event_id"], json.dumps(feedback)))


@lru_cache(maxsize=1)
def bearing_bundle():
    return load_bearing_bundle(Path(os.getenv("AXON_BEARING_MODEL_DIR", PROJECT_ROOT / "ml" / "artifacts" / "bearing" / "active")))


class MqttPublisher:
    def __init__(self, client=None): self.client = client or mqtt.Client()
    def connect(self, host, port): self.client.connect(host, port, keepalive=30); self.client.loop_start()
    def close(self): self.client.loop_stop(); self.client.disconnect()
    def publish_command(self, command):
        info = self.client.publish(f"factory/{command.machine_id}/command", command.model_dump_json())
        if info.rc != mqtt.MQTT_ERR_SUCCESS: raise RuntimeError(f"MQTT publish failed ({info.rc})")
        return "published"


def handle_mqtt_message(store, message):
    """Reject malformed MQTT input without terminating the subscriber."""
    parts = message.topic.split("/")
    if len(parts) != 3 or parts[0] != "factory" or parts[2] not in {"telemetry", "alert", "diagnostic"}:
        log.warning("ignored unsupported topic %s", message.topic); return False
    try:
        payload = json.loads(message.payload.decode("utf-8"))
        if parts[2] == "telemetry": store.write_telemetry(Telemetry.model_validate(payload))
        elif parts[2] == "alert": store.write_alert(Alert.model_validate(payload))
        else: store.write_diagnostic(DiagnosticEvent.model_validate(payload).model_dump(mode="json"))
        return True
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        log.warning("ignored invalid MQTT payload: %s", exc); return False


def create_app(store=None, publisher=None, mqtt_enabled=None):
    if store is None:
        store = ExternalStore() if os.getenv("AXON_STORAGE_MODE", "memory") == "external" else MemoryStore()
    publisher = publisher or MqttPublisher()
    mqtt_enabled = os.getenv("MQTT_ENABLED", "1") == "1" if mqtt_enabled is None else mqtt_enabled
    host, port = os.getenv("MQTT_HOST", "localhost"), int(os.getenv("MQTT_PORT", "1883"))

    @asynccontextmanager
    async def lifespan(app):
        app.state.mqtt_ready = False
        if mqtt_enabled:
            publisher.client.on_message = lambda client, userdata, message: handle_mqtt_message(store, message)
            try:
                publisher.connect(host, port)
                publisher.client.subscribe([("factory/+/telemetry", 0), ("factory/+/alert", 0), ("factory/+/diagnostic", 1)])
                app.state.mqtt_ready = True
            except Exception as exc: log.error("MQTT unavailable: %s", exc)
        yield
        if mqtt_enabled and app.state.mqtt_ready: publisher.close()

    app = FastAPI(title="Axon Backend", version="1.0.0", lifespan=lifespan)
    @app.get("/ready")
    def ready(): return {"status": "ready", "mqtt_connected": app.state.mqtt_ready, "storage": type(store).__name__}
    @app.get("/machines")
    def machines(): return store.machines() or ["M1"]
    @app.get("/readings")
    def readings(machine_id: str = Query("M1", min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$"), minutes: int = Query(5, ge=1, le=1440)): return store.readings(machine_id, minutes)
    @app.get("/alerts")
    def alerts(machine_id: str = Query("M1", min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")): return store.alerts(machine_id)
    @app.get("/health")
    def health(machine_id: str = Query("M1", min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")): return compute_health(store.readings(machine_id, 5), len(store.alerts(machine_id)[:10]))
    @app.get("/commands")
    def commands(machine_id: str = Query("M1", min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")): return store.commands(machine_id)
    @app.post("/command")
    def command(payload: Command):
        try: status = publisher.publish_command(payload)
        except Exception as exc: raise HTTPException(503, "MQTT command publication failed") from exc
        store.write_command(payload, status)
        return {"status": status, "machine_id": payload.machine_id, "action": payload.action}
    @app.get("/diagnostics/taxonomy")
    def diagnostic_taxonomy(): return {"version": "axon-bearing-taxonomy-v1", "faults": public_taxonomy()}
    @app.get("/diagnostics/model-status")
    def diagnostic_model_status():
        try:
            bundle = bearing_bundle()
            return {"available": True, "model_version": bundle.metadata["model_version"], "kind": bundle.metadata["kind"], "input_contract": bundle.metadata["input_contract"]}
        except BearingBundleError as exc:
            return {"available": False, "status": "MODEL_UNAVAILABLE", "reason": str(exc)}
    @app.post("/diagnostics/infer")
    def diagnostic_infer(payload: DiagnosticRequest):
        try:
            bundle = bearing_bundle()
            probabilities = bundle.probabilities(payload.signal, payload.sampling_frequency_hz)
            diagnostic = diagnosis_from_probabilities(payload.asset_id, payload.component_id, probabilities, bundle.metadata["model_version"], evidence=[{"kind": "vibration_window", "sampling_frequency_hz": payload.sampling_frequency_hz, "samples": len(payload.signal)}])
        except BearingBundleError as exc:
            diagnostic = unavailable_diagnosis(payload.asset_id, payload.component_id, str(exc))
        except ValueError as exc:
            diagnostic = unavailable_diagnosis(payload.asset_id, payload.component_id, str(exc), status="SENSOR_DATA_INVALID")
        store.write_diagnostic(diagnostic)
        return diagnostic
    @app.get("/diagnostics/history")
    def diagnostic_history(asset_id: str = Query(..., min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$"), limit: int = Query(50, ge=1, le=200)):
        return store.diagnostics(asset_id, limit)
    @app.post("/diagnostics/technician-confirmation")
    def technician_confirmation(payload: TechnicianConfirmation):
        feedback = payload.model_dump() | {"timestamp": datetime.now(timezone.utc).isoformat()}
        store.write_feedback(feedback)
        return {"status": "recorded", "event_id": payload.event_id, "technician_id": payload.technician_id}
    @app.post("/cost-estimates")
    def cost_estimate(payload: CostEstimateRequest): return estimate_cost(**payload.model_dump())
    @app.get("/repair-documents/search")
    def repair_documents(query: str = Query(..., min_length=2, max_length=200), equipment_model: str | None = Query(default=None, max_length=128)):
        documents = search_documents(PROJECT_ROOT / "config" / "repair_documents.json", query, equipment_model)
        return {"documents": documents, "status": "available" if documents else "unavailable", "reason": None if documents else "No applicable, authorized document is configured."}
    return app


app = create_app()
