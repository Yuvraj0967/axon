"""Axon FastAPI backend: validated MQTT ingest, storage, and command API."""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
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


class Command(BaseModel):
    model_config = ConfigDict(extra="forbid")
    machine_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    action: Literal["slow_down", "shutdown", "resume"]
    issued_by: str = Field(default="operator", min_length=1, max_length=64)


class MemoryStore:
    """Bounded storage for tests and explicit local development mode."""
    def __init__(self):
        self.readings_by_machine, self.alerts_by_machine, self.commands_by_machine = {}, {}, {}

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
    if len(parts) != 3 or parts[0] != "factory" or parts[2] not in {"telemetry", "alert"}:
        log.warning("ignored unsupported topic %s", message.topic); return False
    try:
        payload = json.loads(message.payload.decode("utf-8"))
        if parts[2] == "telemetry": store.write_telemetry(Telemetry.model_validate(payload))
        else: store.write_alert(Alert.model_validate(payload))
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
                publisher.client.subscribe([("factory/+/telemetry", 0), ("factory/+/alert", 0)])
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
    return app


app = create_app()
