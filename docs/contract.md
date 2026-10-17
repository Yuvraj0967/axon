# Axon Contract (FROZEN)

Do not change without telling the whole team.

```
MQTT topics
  factory/<machine_id>/telemetry     edge    -> backend
  factory/<machine_id>/alert         edge    -> backend
  factory/<machine_id>/command       backend -> edge

Telemetry {"machine_id":"M1","ts":"2026-10-17T10:00:00+00:00","temp":72.4,"vibration":0.31,"current":4.8}
Alert     {"machine_id":"M1","ts":"2026-10-17T10:00:03+00:00","type":"anomaly","score":0.91}
Command   {"machine_id":"M1","action":"slow_down","issued_by":"operator"}
Allowed actions: slow_down | shutdown | resume

REST API (Laptop 2, port 8000)
  GET  /machines
  GET  /readings?machine_id=M1&minutes=5  -> [{ts,temp,vibration,current}, ...]
  GET  /alerts?machine_id=M1              -> latest 50 alerts
  GET  /health?machine_id=M1              -> {score,temp_slope,minutes_to_limit,status}
  GET  /commands?machine_id=M1            -> latest 20 operator commands
  POST /command {machine_id, action, issued_by}

status is one of: healthy | warning | critical    (score >= 80 | 50-79 | below 50)
```

## Network

- Same Wi-Fi / phone hotspot for all three laptops.
- Ports on Laptop 2: 1883 (MQTT), 8000 (API) required; 8086, 5432 optional.
- Pin `paho-mqtt==1.6.1`.
