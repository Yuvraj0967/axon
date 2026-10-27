# AXON Verify

AXON Verify is a tamper-evident repair verification platform for industrial rotating equipment. It turns "trust me, it's fixed" into a signed, machine-verified repair record — or refuses to close the work order.

## What it does

- **Verify before/after repairs**: Capture vibration evidence before and after a repair, enforce comparability, and apply a conservative policy to produce `VERIFIED` / `NOT_VERIFIED` / `INCONCLUSIVE` / `CANNOT_VERIFY` with explicit reasons.
- **Tamper-evident certificates**: Issue Ed25519-signed certificates (canonical JSON) with QR codes and printable HTML reports. Verify online at `/verify/{id}` or offline with `python -m backend.certificate_verify`.
- **Multi-tenant & secure**: Organisations/sites/assets/components/work orders, RBAC (owner/admin/manager/technician/viewer/customer/api_key), PBKDF2 passwords, revocable session tokens, API keys, audit logging. SQLite-backed by default with Postgres RLS documented as production path.
- **Multiple transports**: Upload/CSV/REST, MQTT with per-device mTLS and tenant-scoped ACLs, and LoRa via the existing gateway path.
- **Honest about limits**: Model scope is binary bearing (`healthy` vs `other_bearing_damage`) within the validated 4,096-sample @ 64 kHz contract. Probabilities are uncalibrated by default (`confidence_calibrated=false`); policy is conservative and disclosed. Demo scenarios use real Paderborn windows reconstructed as examples.

## Quick start (demo)

From repo root with a Python 3.11 venv:

```bash
# Install deps (example)
python -m venv .venv
. .venv/bin/activate  # or .\.venv\Scripts\activate on Windows
pip install -r backend/requirements.txt -r edge/requirements.txt

# Seed demo tenant/data
AXON_PBKDF2_ITERATIONS=10000 python demo/verify/seed.py --reset

# Start API + webapp
AXON_VERIFY_DB=var/axon-verify.db uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

- Webapp: http://localhost:8000/app/
- Public verifier: http://localhost:8000/verify/{certificate_id}
- API docs: http://localhost:8000/docs
- Demo login: `demo@axon.local` / `demo-axon-verify`

Note: `AXON_VERIFY_DB` selects the verification store independently; the legacy telemetry store does not need InfluxDB/Postgres for AXON Verify.

## MQTT with mTLS (optional)

```bash
# Provision CA, broker, and per-device certs + tenant ACLs
python scripts/mqtt_provision.py --out docker/mqtt/certs --devices demo-device-01:org_demo

# Start Mosquitto
docker compose -f docker-compose.mqtt.yml up -d mosquitto

# Run MQTT ingest worker
AXON_VERIFY_DB=var/axon-verify.db python -m backend.mqtt_ingest

# Simulate a device publish (uses provisioned certs)
AXON_VERIFY_DB=var/axon-verify.db \
  MQTT_CLIENT_CERT=docker/mqtt/certs/devices/demo-device-01.crt \
  MQTT_CLIENT_KEY=docker/mqtt/certs/devices/demo-device-01.key \
  MQTT_CA_CERT=docker/mqtt/certs/ca.crt \
  python -m edge.mqtt_publisher --org org_demo --device demo-device-01 --tenant-scope
```

## Offline certificate verification

```bash
python -m backend.certificate_verify path/to/certificate.json --public-key path/to/public.pem
```

## Tests

```bash
AXON_STORAGE_MODE=memory AXON_PBKDF2_ITERATIONS=10000 python -m pytest -q
```

## Model & data provenance

- Packaged model: `ml/artifacts/bearing/active/` (SHA-256 checked, input contract enforced). Classes: `healthy`, `other_bearing_damage`.
- Demo windows from `demo/paderborn/` (CC BY-NC-4.0). Used as reconstructed examples, not recorded before/after repairs.
- No calibration artifact is shipped; `confidence_calibrated=false` with conservative policy.

## Legacy paths

The original Streamlit dashboard and LoRa telemetry paths remain in the repo for compatibility, but AXON Verify is the product path.
