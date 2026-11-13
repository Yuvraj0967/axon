# AXON

An offline early-warning and repair-coordination agent for small factories.

AXON listens to a machine's vibration, learns what normal running looks like for that machine, and warns the owner when it drifts. It then does the legwork of the repair: it explains the warning in plain language, suggests an idle slot, and drafts the technician request and the part enquiry. The owner approves each step. AXON never stops or slows a machine.

It is built for a shop floor with no signal. Inference runs on a Raspberry Pi-class device, results travel over LoRa with store-and-forward, and raw vibration never leaves the device.

## The problem

The owner of a powerloom, flour mill or pump set is also the maintenance department, and judges machine health by sound and feel. Machines run until they fail, and every breakdown is unplanned:

- **Lost production days.** Deliveries are missed while the owner hunts for a free mechanic.
- **Emergency prices.** Someone is sent to town for the part and pays whatever it costs that day.
- **Idle wages.** Workers are paid to stand beside a machine that is not running.

Usual predictive maintenance does not fit these shops. It needs labelled examples of past failures, a cloud connection, and an engineer to read the charts. Ageing second-hand machines have no failure history, so AXON models healthy behaviour per machine and flags drift away from it.

### Why bearings first

Rolling-bearing damage causes 40–70% of failures in electric motors and drive systems (Lessmeier et al., 2016, citing earlier reliability studies). Looms, flour mills and pump sets are all motor-driven, so one sensor on one component covers the most common way they fail.

## How it works

1. **Sense.** A vibration sensor on the machine feeds a small edge device.
2. **Learn normal.** A few weeks of healthy running become that machine's baseline.
3. **Flag drift.** The device spots change early and stores it locally.
4. **Agent acts.** It explains the warning and prepares the repair.
5. **Owner decides.** The owner approves each step.

Pipeline: sensor or recorded window → edge device (local model, SQLite outbox) → LoRa v2 binary frame, resent until acknowledged → gateway (SQLite spool, duplicate removal) → API → agent and dashboard.

Only a compact diagnosis is sent, so a power cut or dead network delays a message but does not lose it.

## What is built

| Part | State |
| --- | --- |
| On-device inference, LoRa link with acknowledgement and retry, gateway, backend API, dashboard, technician confirmation record | Built and tested on recorded signals |
| Supervised bearing classifier (packaged Random Forest) | Built; evaluated on held-out physical bearings (see below) |
| Healthy-only baseline detector | Built and unit-tested on synthetic signals. Not yet evaluated on the Paderborn recordings, and no fitted baseline is packaged |
| Repair-coordination agent (warning, idle slot, drafts, owner approval, technician finding) | Built and tested. Messages appear in the dashboard only; no phone, SMS or WhatsApp channel is connected |
| Technician's multi-shop worklist | Built and tested |
| Low-cost sensor on a real loom or mill | Not done. Hardware is simulated with recorded signals from the Paderborn University bearing dataset |

### Model evidence

The packaged classifier takes 4,096 vibration samples at 64,000 Hz, computes 16 engineered features, and outputs `healthy` or `other_bearing_damage`.

On 2,981 test windows from two physical bearings held out of training (K003 and KI04):

- accuracy 95.30%, macro F1 0.9529
- 0 false alarms across 1,493 healthy windows
- 90.59% of damaged windows caught (140 of 1,488 missed)

These are laboratory results. Class probabilities are uncalibrated, and no race-level diagnosis, failure-time prediction or new-sensor validation is claimed.

### Healthy-only baseline

`ml/bearing/baseline.py` fits an Isolation Forest on the same 16 features using only windows of normal running from one machine, and sets its alarm threshold from held-back healthy windows. It reports which measurements changed, which the agent turns into plain language.

When a fitted baseline exists for a machine, the edge runner uses it as the primary detector and the supervised classifier only adds a hint about the kind of damage. Without one, the classifier decides on its own, which is what the packaged demo does. See [docs/HEALTHY_BASELINE.md](docs/HEALTHY_BASELINE.md).

### Agent

After at least 3 of a machine's last 5 results are abnormal, the agent raises a repair proposal:

> Loom 3: the motor-side bearing has been running differently from normal for 4 days — there are sharp knocks in the vibration. Sunday 15 Nov, 08:00–18:00, is idle. Shall I ask the technician and check the part?

The owner answers each step with Approve or Not now. A "not now" is raised again after 24 hours if the warning persists. The technician's finding closes the proposal and records whether the machine's baseline needs correcting. Messages are written in English or Hindi according to the shop's setting. The agent is rule-based and needs no internet. See [docs/AGENT.md](docs/AGENT.md).

## Who benefits

- **Owner:** fewer lost days, and repairs done in idle hours.
- **Technician:** a ranked list of machines about to fail across many shops, so the week is planned and parts are stocked ahead.
- **Parts dealer:** orders known in advance, not rush requests.

A technician or dealer who serves many shops can carry AXON to owners who would never buy monitoring on their own.

## Run the demo (Windows, from the repository root)

Use Python 3.12 and the project virtual environment:

~~~powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt -r edge/requirements.txt -r dashboard/requirements.txt
.\scripts\start_demo.ps1
~~~

Open http://127.0.0.1:8501. The launcher uses memory storage, so Docker is optional and history disappears when the API stops. Set `AXON_STORAGE_MODE=external` with the Docker Compose services for persistent storage.

To exercise the whole path without radio hardware:

~~~powershell
.\.venv\Scripts\python.exe -m edge.bearing_runner --transport loopback --interval 5
~~~

This alternates a documented healthy recording (K001) and a documented damaged one (KA04) for asset `demo-motor-001`. It runs local inference, binary encoding, CRC, durable gateway receipt, ACK and HTTP delivery.

The dashboard has four workspaces:

- **Paderborn data replay:** classify a chosen historical window.
- **Bearing diagnosis:** the latest result for a machine, with history.
- **Repair approvals:** the agent's proposals, with Approve and Not now for each step. A proposal for "Loom 3" appears after a few runner results.
- **Technician worklist:** every machine a technician serves across shops, ranked, with a form to record the finding.

The demo uses the example shop registry in `config/shops.example.json`. Copy it to `config/shops.json` and enter your own shops, machines, idle hours, technician and dealer.

The packaged model is under `ml/artifacts/bearing/active`. Its SHA-256, input contract and training library version are checked on load. The API and the Pi use the same requirements. No retraining is needed to run the demo.

## Hardware boundary

On a Pi 4 use `python -m edge.bearing_runner --transport lora --port /dev/serial0`. The default source is historical recordings. Live capture requires `--source capture` and a hardware-specific `--capture-command` that returns a calibrated, hardware-clocked vibration window. No sensor or ADC model has been specified or physically validated. Python does not time 64 kS/s acquisition. See [docs/DEMO.md](docs/DEMO.md) for the provider contract.

Run `python -m edge.lora_gateway --port COM5` on a Windows USB-UART gateway, or use the appropriate `/dev/serial0` device on Linux. Upgrade sender and gateway together: v2 replaced the earlier 13-byte packet.

Machine commands return HTTP 501. AXON has no actuator downlink and is not meant to have one.

## Legacy code

`edge/simulator.py` and the Isolation Forest in `ml/artifacts/latest` are earlier synthetic-telemetry examples. They post HTTP telemetry and are not part of the bearing path. They are unrelated to the healthy-only bearing baseline in `ml/bearing/baseline.py`.

## Tests

~~~powershell
$env:AXON_STORAGE_MODE = "memory"
.\.venv\Scripts\python.exe -m pytest
~~~

## What comes next

1. Fit and evaluate the healthy-only baseline on the full Paderborn recordings, then on a real machine, and make it the default detector.
2. Deliver the agent's messages to the owner's phone, and add more local languages.
3. Validate on a low-cost sensor fitted to a real loom or mill.
4. Extend the technician's view with parts stocking across shops.

## Research behind the approach

- Lessmeier, Kimotho, Zimmer and Sextro, PHM Society European Conference, 2016. The Paderborn bearing benchmark, source of the recorded signals.
- Liu, Ting and Zhou, "Isolation Forest", IEEE ICDM, 2008. Anomaly detection that needs no fault labels, the basis of the healthy-only baseline.
- Sensors 25(21):6610, MDPI, 2025. Low-cost microcontroller and MEMS sensors running anomaly detection on the device.
- Leroux and Simoens, Electronics 13(24):5034, 2024. Models trained only on healthy bearings, deployed at the edge across a fleet of machines.

The Paderborn data is licensed CC BY-NC 4.0. See [demo/paderborn/README.md](demo/paderborn/README.md) for provenance.

## More documentation

[Architecture](docs/ARCHITECTURE.md) · [Healthy baseline](docs/HEALTHY_BASELINE.md) · [Agent](docs/AGENT.md) · [Wire contract](docs/contract.md) · [Demo walkthrough](docs/DEMO.md) · [Bearing diagnosis](docs/BEARING_DIAGNOSIS.md) · [Testing](docs/TESTING.md)
