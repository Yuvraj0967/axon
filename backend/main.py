import json
from fastapi import FastAPI
from pydantic import BaseModel
import paho.mqtt.client as mqtt
import psycopg2
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

app = FastAPI(title="Axon Backend")

influx = InfluxDBClient(url="http://localhost:8086", token="axon-token", org="axon")
write_api = influx.write_api(write_options=SYNCHRONOUS)
query_api = influx.query_api()

pg = psycopg2.connect(host="localhost", dbname="axon", user="axon", password="axonpass")
pg.autocommit = True
with pg.cursor() as cur:
    cur.execute("CREATE TABLE IF NOT EXISTS alerts (id SERIAL PRIMARY KEY, machine_id TEXT,"
                " ts TEXT, type TEXT, score REAL)")
    cur.execute("CREATE TABLE IF NOT EXISTS commands (id SERIAL PRIMARY KEY, machine_id TEXT,"
                " action TEXT, issued_by TEXT, created TIMESTAMP DEFAULT now())")

mqttc = mqtt.Client()

def on_message(client, userdata, msg):
    d = json.loads(msg.payload)
    kind = msg.topic.split("/")[2]
    if kind == "telemetry":
        p = (Point("telemetry").tag("machine_id", d["machine_id"])
             .field("temp", float(d["temp"]))
             .field("vibration", float(d["vibration"]))
             .field("current", float(d["current"])))
        write_api.write(bucket="telemetry", record=p)
    elif kind == "alert":
        with pg.cursor() as cur:
            cur.execute("INSERT INTO alerts (machine_id, ts, type, score) VALUES (%s,%s,%s,%s)",
                        (d["machine_id"], d["ts"], d["type"], d["score"]))

mqttc.on_message = on_message

@app.on_event("startup")
def start_mqtt():
    mqttc.connect("localhost", 1883)
    mqttc.subscribe([("factory/+/telemetry", 0), ("factory/+/alert", 0)])
    mqttc.loop_start()

import sys
sys.path.append("../shared")          # Person 1 delivers shared/health.py
from health import compute_health

@app.get("/machines")
def machines():
    return ["M1"]

@app.get("/readings")
def readings(machine_id: str = "M1", minutes: int = 5):
    q = ('from(bucket:"telemetry") |> range(start: -%dm) '
         '|> filter(fn:(r) => r.machine_id == "%s") '
         '|> pivot(rowKey:["_time"], columnKey:["_field"], valueColumn:"_value")') % (minutes, machine_id)
    out = []
    for table in query_api.query(q):
        for r in table.records:
            out.append({"ts": r.get_time().isoformat(), "temp": r.values.get("temp"),
                        "vibration": r.values.get("vibration"), "current": r.values.get("current")})
    return sorted(out, key=lambda r: r["ts"])

@app.get("/alerts")
def alerts(machine_id: str = "M1"):
    with pg.cursor() as cur:
        cur.execute("SELECT machine_id, ts, type, score FROM alerts WHERE machine_id=%s"
                    " ORDER BY id DESC LIMIT 50", (machine_id,))
        return [dict(zip(["machine_id", "ts", "type", "score"], row)) for row in cur.fetchall()]

@app.get("/health")
def health(machine_id: str = "M1"):
    rows = readings(machine_id, 5)
    with pg.cursor() as cur:
        cur.execute("SELECT count(*) FROM (SELECT 1 FROM alerts WHERE machine_id=%s"
                    " ORDER BY id DESC LIMIT 10) t", (machine_id,))
        n = cur.fetchone()[0]
    return compute_health(rows, n)

@app.get("/commands")
def commands(machine_id: str = "M1"):
    with pg.cursor() as cur:
        cur.execute("SELECT machine_id, action, issued_by, created FROM commands WHERE machine_id=%s"
                    " ORDER BY id DESC LIMIT 20", (machine_id,))
        return [{"machine_id": a, "action": b, "issued_by": c, "created": str(d)}
                for a, b, c, d in cur.fetchall()]

class Cmd(BaseModel):
    machine_id: str
    action: str
    issued_by: str = "operator"

@app.post("/command")
def command(cmd: Cmd):
    mqttc.publish(f"factory/{cmd.machine_id}/command", json.dumps(cmd.dict()))
    with pg.cursor() as cur:
        cur.execute("INSERT INTO commands (machine_id, action, issued_by) VALUES (%s,%s,%s)",
                    (cmd.machine_id, cmd.action, cmd.issued_by))
    return {"status": "sent"}
