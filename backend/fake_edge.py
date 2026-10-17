import json, time, random
import paho.mqtt.client as mqtt

c = mqtt.Client()
c.connect("localhost", 1883)
c.loop_start()
while True:
    c.publish("factory/M1/telemetry", json.dumps({"machine_id": "M1", "ts": "x",
        "temp": 72 + random.random(), "vibration": 0.3, "current": 4.8}))
    if random.random() < 0.1:
        c.publish("factory/M1/alert", json.dumps({"machine_id": "M1",
            "ts": "x", "type": "anomaly", "score": 0.8}))
    time.sleep(1)
