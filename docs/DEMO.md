# Demonstration

1. Start Docker, train the model, start FastAPI, simulator, and dashboard using the commands in the README.
2. Confirm fresh telemetry and healthy status in the dashboard.
3. In the edge terminal type `f` then Enter. Sensor values rise and anomaly alerts are emitted.
4. Verify the alert feed and health score update from backend data.
5. Click Slow Down and verify the edge prints `COMMAND RECEIVED`; subsequent telemetry falls.
6. Confirm the simulated Shutdown control, then use Resume and observe telemetry return.

Recovery: if MQTT is unavailable, confirm `MQTT_HOST` and port 1883, then restart Mosquitto. For a UI-only backup run `python dashboard/make_mock.py`, set `USE_MOCK=1`, and clearly state that it is mock data.
