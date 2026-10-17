# Axon

Axon is a demonstration-grade industrial-machine intelligence layer: an edge simulator publishes telemetry and calibrated anomaly alerts over MQTT; FastAPI exposes operator data; Streamlit visualizes health and sends simulated commands.

## Architecture

`edge simulator -> MQTT broker -> FastAPI -> InfluxDB/PostgreSQL -> Streamlit dashboard`

The shared MQTT and REST interface is frozen in [docs/contract.md](docs/contract.md). This is not a safety controller or a validated predictive-maintenance product.

## Single-machine startup

1. Copy `.env.example` to `.env` and replace all `change-me-before-demo` values.
2. Start infrastructure: `cd backend; docker compose --env-file ../.env up -d`
3. Install dependencies: `python -m pip install -r backend/requirements.txt -r edge/requirements.txt -r dashboard/requirements.txt`

4. Train the offline model once: `python -m ml.training.train --generate-synthetic`
5. From the repository root start the API: `python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000`
6. From the repository root start the edge: `python edge/simulator.py` and type `f` then Enter to inject a fault.
7. Start the dashboard: `streamlit run dashboard/app.py`

The current edge model is the validated artifact under `ml/artifacts/latest`; the simulator refuses to invent a new model at startup.

## Real-world training data

The committed starter artifact uses deterministic synthetic telemetry only for
offline development. For the deployment model, use the real-world UCI
MetroPT-3 dataset: compressor telemetry from an operating Porto metro train
with pressure, oil-temperature, motor-current, and operator-reported failure
windows. It is CC BY 4.0 and is not committed because the source CSV is about
208 MB.

1. Download `MetroPT3(AirCompressor).csv` from https://doi.org/10.24432/C5VW3R.
2. Prepare a labelled local table:
   `python -m ml.data.metropt3 --input path/to/MetroPT3(AirCompressor).csv`
3. Train a MetroPT-3 artifact:
   `python -m ml.training.train --dataset ml/data/metropt3/metropt3_prepared.csv --output ml/artifacts/metropt3 --features pressure,oil_temperature,motor_current`

The adapter retains three measured signals (`pressure`, `oil_temperature`, and
`motor_current`) and labels only the four failure intervals published by the
dataset operator. It does not manufacture a vibration signal.

## Testing

Run `python -m pytest`. The suite validates health scoring, malformed MQTT rejection, command API behavior, artifact training, and fault inference. Full Docker/MQTT/database integration must be run separately on a host with Docker available; see [docs/TESTING.md](docs/TESTING.md).

## Three-laptop demo

Laptop 2 runs Docker and the API. Set `MQTT_HOST=<laptop-2-ip>` on Laptop 1 and `BACKEND_URL=http://<laptop-2-ip>:8000` on Laptop 3. All laptops must be on the same LAN; expose only ports 1883 and 8000 for the demo. See [docs/DEMO.md](docs/DEMO.md).

## Known limitations

- The synthetic training data supports development and demonstration only; it is not evidence of real-machine accuracy.
- Commands are broker-publication acknowledgements; actual simulator execution must be observed from edge output or subsequent telemetry.
- The local test mode uses bounded in-memory storage. Set `AXON_STORAGE_MODE=external` to use InfluxDB and PostgreSQL from Docker.
