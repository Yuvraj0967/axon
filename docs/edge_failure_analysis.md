# Edge failure analysis

| Scenario | Current observed/inspected behavior | Safety status |
| --- | --- | --- |
| Corrupt or incomplete artifact | `load_predictor` raises `ArtifactLoadError`; the edge process refuses startup. | Verified by artifact loader validation; no false normal decision is emitted. |
| Missing/non-finite model feature | `Predictor.predict_one` raises `ValueError`. | Verified by code and unit coverage; caller needs an explicit unverified alert/state. |
| Malformed MQTT telemetry | Backend validation rejects the message and logs a warning. | Verified by `handle_mqtt_message`; no retention/degraded dashboard state. |
| Broker unavailable | Edge `connect` currently fails startup; no local durable queue exists. | Unverified end-to-end recovery; deployment blocker for intermittent networks. |
| Duplicate/out-of-order/stale telemetry | The generator can publish these. Backend has no idempotency or freshness check. | Inspected gap; may distort history and alerts. |
| CPU/memory/disk exhaustion | Docker limits are configured, but this Windows AMD64 host has not supplied Linux cgroup evidence. | Unverified until Linux/ARM test. |
| API/database unavailable | Edge inference and MQTT can continue, but server-side persistence/dashboard may not. | Unverified end-to-end retry behavior. |

The current contract has no `unverified` state. Do not interpret missing data,
rejected messages, or a stopped edge process as a healthy machine. Add a bounded
queue, explicit stale timeout, retry policy, and dashboard exposure before a
safety-sensitive deployment.
