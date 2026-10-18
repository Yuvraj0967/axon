# AXON bearing diagnostics

AXON classifies vibration windows with a packaged Paderborn Random Forest and shows the result, waveform, features and affected bearing assembly in a Streamlit dashboard.

## Presentation startup (Windows, from repository root)

Use Python 3.12 and the project virtual environment:

~~~powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt -r edge/requirements.txt -r dashboard/requirements.txt
.\scripts\start_demo.ps1
~~~

Open http://127.0.0.1:8501. The launcher explicitly uses memory storage, so Docker is optional for this demo and diagnostic history disappears when the API stops. Use AXON_STORAGE_MODE=external with the existing Docker Compose services for persistent storage.

The packaged model is under ml/artifacts/bearing/active. Its SHA-256, input contract and training library version are checked. The API and Pi use the same requirements. No retraining or synthetic data generation is required to run it.

## Integrated bearing path

Hardware capture provider or recorded Paderborn window → local model → SQLite outbox → LoRa v2 binary frame → gateway SQLite spool → API diagnostic history → dashboard.

For a repeatable demonstration without radio hardware, run:

~~~powershell
.\.venv\Scripts\python.exe -m edge.bearing_runner --transport loopback --interval 5
~~~

Open **Bearing diagnosis**, asset **demo-motor-001**. This alternates held-out K003 and KI04 recordings. It exercises local inference, binary encoding, CRC, durable gateway receipt, ACK and HTTP delivery. The UI labels it as software radio replay and shows one-decimal model vote confidence. Ctrl+C stops it. Confidence is not probability-calibrated and must not be presented as certainty.

The **Paderborn data replay** workspace uses the full locally prepared dataset if available, otherwise eight packaged, attributed windows from four recordings. See demo/paderborn/README.md for provenance and noncommercial data licence.

## Hardware boundary

On a Pi 4 use python -m edge.bearing_runner --transport lora --port /dev/serial0. The default source is historical recordings. Live capture requires --source capture and a hardware-specific --capture-command that returns a calibrated, hardware-clocked vibration window. No sensor/ADC model has been specified or physically validated here. Python does not time 64 kS/s acquisition. See docs/DEMO.md for the provider contract.

Run python -m edge.lora_gateway --port COM5 on a Windows USB-UART gateway, or use the appropriate /dev/serial0 device on Linux. Upgrade sender and gateway together: v2 replaces the earlier 13-byte packet. It supports arbitrary asset/component IDs, model identity, diagnostic status and event-unique ACK/deduplication.

## Model evidence

Input: 4,096 vibration samples at 64,000 Hz → 16 engineered features.
Output: healthy or other_bearing_damage. No race-level diagnosis, failure-time prediction or new-sensor validation is claimed.

The stored held-out-physical-bearing test report covers 2,981 windows from K003 and KI04: accuracy 95.30%, macro F1 0.9529, damage recall 90.59% (140 damaged windows missed). Class probabilities are uncalibrated.

The older edge/simulator.py and ml/artifacts/latest Isolation Forest are legacy synthetic telemetry examples. They POST HTTP telemetry; they are not part of this bearing demo and do not send bearing diagnoses over LoRa. Their health and alert endpoints remain for compatibility. Machine commands return HTTP 501 because no LoRa actuator downlink exists.

## Verification

~~~powershell
$env:AXON_STORAGE_MODE = "memory"
.\.venv\Scripts\python.exe -m pytest
~~~

See docs/contract.md for the v2 wire contract and docs/DEMO.md for the presentation walkthrough.
