# Troubleshooting

- MQTT connection refused: confirm Docker is running, `MQTT_HOST` is Laptop 2's LAN IP for remote edge machines, and port 1883 is allowed by the firewall.
- Dashboard unavailable: open `http://<backend-ip>:8000/docs` from Laptop 3 and confirm the API was started with `--host 0.0.0.0`.
- No data: use `python backend/fake_edge.py --count 3` to isolate broker/backend ingestion from the real simulator.
- Edge will not start: generate `ml/artifacts/latest` with `python -m ml.training.train --generate-synthetic` and install `edge/requirements.txt`.
- Docker services fail: inspect `docker compose logs`, confirm ports 1883 and 8086 are unused, and replace default development passwords in `.env`.
