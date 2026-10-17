# Axon

**The nervous system for existing machines.**

Open-source, hardware-agnostic intelligence layer for industrial machinery: TinyML edge AI,
MQTT, FastAPI, InfluxDB/PostgreSQL and a live operator dashboard. We do not replace the machines;
we give them an intelligence layer.

## Architecture (3 laptops)

    Laptop 1 (edge)       Laptop 2 (backend + data)         Laptop 3 (dashboard)
    simulator + model --> Mosquitto, FastAPI, InfluxDB, <-- Streamlit dashboard
    command listener <--  PostgreSQL  (Docker)              operator buttons

| Folder | Owner | Laptop |
|---|---|---|
| edge/, shared/ | Person 1 | Laptop 1 |
| backend/ | Person 2 | Laptop 2 |
| dashboard/, docs/ | Person 3 | Laptop 3 |

Read `docs/contract.md` first. Track progress in `docs/TASKS.md`.
Each person works on a branch (`feature/edge`, `feature/backend`, `feature/dashboard`) and commits only inside their own folder.

## Quick start

    # Laptop 2
    cd backend && docker compose up -d && pip install -r requirements.txt
    uvicorn main:app --host 0.0.0.0 --port 8000

    # Laptop 1
    cd edge && pip install -r requirements.txt
    export BROKER_IP=<LAPTOP2_IP> && python simulator.py     # type f + Enter to inject a fault

    # Laptop 3
    cd dashboard && pip install -r requirements.txt
    export BACKEND_IP=<LAPTOP2_IP> && streamlit run app.py   # USE_MOCK=1 to run without a backend
