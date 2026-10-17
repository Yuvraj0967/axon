# Backend and data (Person 2)

    docker compose up -d
    pip install -r requirements.txt
    uvicorn main:app --host 0.0.0.0 --port 8000     # then open http://localhost:8000/docs
    python fake_edge.py                              # fake telemetry for testing without Laptop 1

`/health` imports `../shared/health.py` (Person 1).
InfluxDB UI: http://localhost:8086 (admin / adminpass123, demo only).
