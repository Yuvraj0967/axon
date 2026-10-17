# Architecture

Axon separates offline ML training from edge inference. `ml/data` creates or validates datasets, `ml/training` fits and calibrates a scikit-learn Isolation Forest, `ml/artifacts/latest` holds the trusted model and metadata, and `ml/inference` validates artifacts and scores each edge observation.

The edge process generates temperature, vibration, and current once per second, publishes the frozen telemetry payload, and publishes an alert when its persisted threshold is crossed. It subscribes only to `factory/M1/command`.

The backend validates MQTT payloads before storage and exposes contract endpoints. The dashboard never falls back to mock data when a live backend fails. MQTT publication confirms broker delivery, not physical command execution.

For the three-laptop deployment, Laptop 1 and Laptop 3 talk only to Laptop 2. PostgreSQL should remain internal; only 1883 and 8000 need LAN access.
