"""Predictable MQTT publisher for backend integration testing, not the real edge model."""
import argparse, json, os, random, time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--machine-id", default="M1")
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--scenario", choices=("normal", "fault"), default="normal")
    parser.add_argument("--count", type=int, default=0, help="zero publishes forever")
    args = parser.parse_args()
    random.seed(42)
    client = mqtt.Client(); client.connect(os.getenv("MQTT_HOST", "localhost"), int(os.getenv("MQTT_PORT", "1883"))); client.loop_start()
    try:
        for index in range(args.count or 2**31):
            fault = args.scenario == "fault"
            reading = {"machine_id": args.machine_id, "ts": datetime.now(timezone.utc).isoformat(), "temp": round(75 + random.gauss(0, 1) + (25 if fault else 0), 2), "vibration": round(.3 + random.gauss(0, .03) + (.6 if fault else 0), 3), "current": round(4.5 + random.gauss(0, .2) + (2 if fault else 0), 2)}
            client.publish(f"factory/{args.machine_id}/telemetry", json.dumps(reading))
            if fault: client.publish(f"factory/{args.machine_id}/alert", json.dumps({"machine_id":args.machine_id,"ts":reading["ts"],"type":"anomaly","score":0.9}))
            print(json.dumps(reading)); time.sleep(args.interval)
    except KeyboardInterrupt: pass
    finally: client.loop_stop(); client.disconnect()


if __name__ == "__main__": main()
