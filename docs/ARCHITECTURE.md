# Architecture

AXON has five stages. Each one stores its output before handing it on, so a power cut or dead link delays a result but does not lose it.

| Stage | Code | What it does |
| --- | --- | --- |
| Sensor | `edge/bearing_runner.py` | Reads a vibration window from a hardware capture provider, or replays a recorded Paderborn window. Simulated today. |
| Edge device | `edge/bearing_inference.py`, `ml/bearing/` | Runs the detector locally and queues the result in a SQLite outbox. Raw vibration stays here. |
| LoRa radio | `shared/lora_protocol.py`, `edge/lora_transport.py` | Sends a compact v2 binary frame with CRC-16 and resends until acknowledged. |
| Gateway | `edge/lora_gateway.py` | Validates the frame, stores it in a SQLite spool, drops duplicates, acknowledges, and posts the typed record to the API. |
| Backend, agent and dashboard | `backend/main.py`, `agent/`, `dashboard/app.py` | Stores history per machine, runs the repair-coordination agent, and serves the owner and technician views. |

## Detection

Two detectors share the 16 engineered features in `ml/bearing/signal.py`:

- The **healthy-only baseline** (`ml/bearing/baseline.py`) is fitted per machine on normal running and flags drift. When one is fitted for a machine it is the primary detector. See [HEALTHY_BASELINE.md](HEALTHY_BASELINE.md).
- The **supervised classifier** (`ml/bearing/bundle.py`, packaged in `ml/artifacts/bearing/active`) was trained on labelled Paderborn recordings. It decides alone when no baseline exists, and otherwise only hints at the kind of damage.

Both produce the same diagnostic record (`shared/diagnosis.py`), so the radio frame, gateway and API do not depend on which detector ran.

## Agent

The backend runs the agent on every diagnostic it ingests. The agent reads the machine's history and the shop registry, and may create or refresh a repair proposal. The owner approves each step through the API or dashboard, and the technician's finding closes it. See [AGENT.md](AGENT.md).

The agent has no path to a machine. LoRa carries diagnostics uplink only, and an acknowledgement confirms gateway receipt, not a repair or any actuator action.

## Storage and deployment

In memory mode the API keeps everything in process, which suits the demo and tests. In external mode it uses InfluxDB for legacy telemetry and PostgreSQL for alerts, diagnostics, technician feedback and agent proposals.

The Pi and gateway communicate over LoRa; the gateway and dashboard use the API. PostgreSQL should stay internal, and only API port 8000 needs LAN access. The dashboard never falls back to mock data when the backend fails.

## Legacy path

`ml/data`, `ml/training`, `ml/inference`, `ml/artifacts/latest` and `edge/simulator.py` are an earlier synthetic-telemetry example built around a separate Isolation Forest. They are kept for compatibility and are not part of the bearing path.
