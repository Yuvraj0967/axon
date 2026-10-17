# Axon Contract (FROZEN)

Do not change without telling the whole team.

## LoRa diagnostic frame

The Pi 4 must run the bearing model locally. It sends a fixed 13-byte binary
diagnostic summary over the Waveshare SX1262/Ebyte E22 transparent UART link;
it does **not** send raw vibration samples.

```
<HBBBHIH (little endian)
asset_id | component_id | fault_class | confidence 0-100 | sequence | Unix timestamp | CRC-16/CCITT
  2 B          1 B            1 B             1 B            2 B        4 B             2 B
```

The gateway validates CRC-16, de-duplicates `(asset_id, sequence)`, persists
the record before acknowledgement, and responds with a 6-byte acknowledgement:
`<HHH` (`asset_id`, `sequence`, `CRC-16/CCITT`). The Pi retains a diagnostic in
its SQLite outbox until this ACK is received.

Current maps are defined in `shared/lora_protocol.py`: `demo-motor-001=1`,
`bearing-drive-end=1`, and `other_bearing_damage=4`.

```
REST API (gateway/API host, port 8000)
  POST /ingest/telemetry                    -> gateway/simulator to backend
  POST /ingest/alert                        -> gateway/simulator to backend
  POST /ingest/diagnostic                   -> LoRa gateway to backend
  GET  /machines
  GET  /readings?machine_id=M1&minutes=5  -> [{ts,temp,vibration,current}, ...]
  GET  /alerts?machine_id=M1              -> latest 50 alerts
  GET  /health?machine_id=M1              -> {score,temp_slope,minutes_to_limit,status}
  GET  /commands?machine_id=M1            -> latest 20 operator commands
  POST /command {machine_id, action, issued_by}  -> queued_for_lora

status is one of: healthy | warning | critical    (score >= 80 | 50-79 | below 50)
```

## Network

- Pi 4 and the gateway use paired 868 MHz transparent-UART LoRa modules on a
  channel within the locally permitted 865–867 MHz range. Attach antennas
  before powering either radio.
- The LoRa packet is point-to-point; no network server or broker is used.
- Gateway-to-API traffic uses port 8000. Ports 8086 and 5432 remain optional.
