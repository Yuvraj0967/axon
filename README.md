# Axon

Axon is a demonstration-grade industrial-machine intelligence layer: a Raspberry Pi 4 performs local bearing inference, sends compact diagnostic summaries over a transparent-UART LoRa link, and a gateway forwards validated records to FastAPI for the operator dashboard.

## Architecture

`sensor/ADC -> Raspberry Pi 4 inference -> LoRa UART radio -> gateway HTTP ingest -> FastAPI -> storage -> Streamlit dashboard`

The LoRa packet and REST ingest interface is defined in [docs/contract.md](docs/contract.md). This is not a safety controller or a validated predictive-maintenance product.

## Single-machine startup

1. Copy `.env.example` to `.env` and replace all `change-me-before-demo` values.
2. Start infrastructure: `cd backend; docker compose --env-file ../.env up -d`
3. Install dependencies: `python -m pip install -r backend/requirements.txt -r edge/requirements.txt -r dashboard/requirements.txt`

4. Train the offline model once: `python -m ml.training.train --generate-synthetic`
5. From the repository root start the API: `python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000`
6. On the Pi/gateway, run `python edge/lora_gateway.py --port /dev/serial0`. The generic simulator remains available with `python edge/simulator.py` and `f` then Enter to inject a non-bearing telemetry fault.
7. Start the dashboard: `streamlit run dashboard/app.py`

The current edge model is the validated artifact under `ml/artifacts/latest`; the simulator refuses to invent a new model at startup.

## Bearing diagnosis extension

Paderborn Bearing DataCenter vibration recordings are AXON's only supported
real-world training-data path. The workflow prepares locally acquired MATLAB
recordings with an explicit fact-sheet label mapping, trains a physical-bearing
held-out Random Forest or optional 1D CNN, and sends local Pi diagnostic
summaries through a dedicated LoRa packet. Source recordings are local-only and no
bearing classifier is claimed as trained until a valid bundle exists.

See [the bearing diagnosis workflow and evidence boundaries](docs/BEARING_DIAGNOSIS.md).

## Testing

Run `python -m pytest`. The suite validates health scoring, LoRa packet CRC/ACK behavior, REST ingest, artifact training, and fault inference. Full Docker/database integration must be run separately on a host with Docker available; see [docs/TESTING.md](docs/TESTING.md).

## Three-laptop demo

The LoRa gateway forwards to the API over `BACKEND_URL=http://<gateway-or-api-ip>:8000`. Only port 8000 is needed between the gateway and the dashboard; the Pi-to-gateway diagnostic link is LoRa.

## Known limitations

- The synthetic training data supports development and demonstration only; it is not evidence of real-machine accuracy.
- Commands are queued for a LoRa-enabled edge receiver; actual execution must be observed from edge output or subsequent telemetry.
- The local test mode uses bounded in-memory storage. Set `AXON_STORAGE_MODE=external` to use InfluxDB and PostgreSQL from Docker.
