# 02 — Hidden Strategic Assets

**Question:** ignoring the current "bearing diagnostics" marketing, what can this system already do that is expensive, hard, or rare?

---

## 1. The central reframing

The visible product is: *"upload/replay a vibration window, get a bearing diagnosis."*  
The hidden asset is: *"a physical-world decision can be produced offline, validated against a strict input/model contract, represented with uncertainty and provenance, transported reliably over an intermittent link, and audited later."*

The classifier is the least defensible part. The **decision record and its delivery chain** are the more interesting asset. That is the asset a pivot should center.

---

## 2. Asset inventory and ranking

Scores are 1–5; higher is better. "Uniqueness" means how hard it is for a typical hackathon team to reproduce, not how hard it is for Augury.

| Rank | Asset | What it actually is | Reuse | Uniqueness | Build cost if absent | User value | Strategic verdict |
|---:|---|---|---:|---:|---:|---:|---|
| 1 | **Auditable diagnostic record + status taxonomy** (`shared/diagnosis.py`, `backend/main.py` models) | A typed record with fault, confidence, calibration flag, alternatives, missing information, confirmation tests, model version, simulated flag, evidence list | 5 | 4 | Medium | 5 | **Core asset.** Turns a prediction into a defensible decision object. |
| 2 | **Durable edge outbox + gateway spool + idempotent relay** (`edge/lora_transport.py`, `edge/lora_gateway.py`) | At-least-once event delivery with SQLite persistence, event-id dedupe, ACK after persistence, retry after API failure | 5 | 5 | High | 4 | **Core asset.** Rare in hackathon code; enables offline/remote trust. |
| 3 | **Compact binary protocol with CRC and typed statuses** (`shared/lora_protocol.py`) | Variable-length v2 frame, UUID, sequence, timestamp, model version, fault/status enums, ACK | 5 | 4 | Medium | 3 | Reuse; makes the offline story real. |
| 4 | **Strict model/input contract and bundle validation** (`ml/bearing/bundle.py`) | Exact window/sample rate, feature order, artifact hash, library version, schema; explicit refusal | 5 | 3 | Medium | 4 | **Trust primitive.** Prevents silent wrong-model deployment. |
| 5 | **Uncertainty-aware decision policy** (`shared/diagnosis.py`) | Threshold 0.70; `DIAGNOSIS_UNCERTAIN`, `MODEL_UNAVAILABLE`, `SENSOR_DATA_INVALID`; never a false healthy | 5 | 4 | Low | 5 | **Differentiator in a demo:** the system can refuse. |
| 6 | **Provenance-rich replay/manifest** (`backend/paderborn_replay.py`, `demo/paderborn/manifest.json`) | License, source, checksums, documented labels, window indices, replay flag | 4 | 4 | Medium | 3 | Reuse for honest demo; not a moat by itself. |
| 7 | **Vibration feature pipeline** (`ml/bearing/signal.py`) | 16 time/frequency features, validation, segmentation | 5 | 2 | Low | 3 | Commodity; reuse as plumbing. |
| 8 | **Grouped, leakage-resistant evaluation** (`ml/bearing/training.py`) | Physical-bearing split; requires 3 bearings/class; metrics/report | 4 | 3 | Medium | 3 | Reuse for credibility; data license limits commercial use. |
| 9 | **Honest dashboard decision UX** (`dashboard/app.py`) | Uncertainty display, source labels, confidence cap, component schematic | 4 | 3 | Medium | 4 | Reuse shell; the workflow is missing. |
| 10 | **Technician feedback endpoint** (`/diagnostics/technician-confirmation`) | Stores confirm/reject/inspection/repair outcome | 3 | 2 | Low | 3 | **Underused asset.** Could close the loop; currently write-only. |
| 11 | **Legacy Isolation Forest + telemetry** | Synthetic anomaly scoring, health score, Influx/Postgres | 2 | 1 | Low | 1 | Demote; do not build the pitch on it. |
| 12 | **Repair docs/cost stubs** | Empty JSON catalog; deterministic cost sum | 2 | 1 | Low | 2 | Not a capability; remove from narrative or implement. |

---

## 3. The compound asset (the one that matters)

No single component is world-changing. The combination is:

> **Offline edge inference + strict model contract + uncertainty policy + durable delivery + provenance record + human confirmation.**

That combination can answer a question most AI demos cannot:

> *"Can you prove what the machine's condition was, what model decided, what evidence was used, whether the decision was uncertain, and that the record was not silently changed?"*

This is a **verification** capability, not a prediction capability. It is the raw material for several product categories: repair closure, asset handover, warranty adjudication, regulatory audit, and model deployment assurance.

---

## 4. What is genuinely expensive to reproduce

| Capability | Why it is non-trivial | Evidence in repo |
|---|---|---|
| Correct offline delivery semantics | Requires queue-before-send, ACK-after-persist, event-id identity, dedupe, retry, restart behavior | Tests: no-ACK restart, API offline retry, duplicate/conflict, sequence wrap |
| Refusal semantics | Most demos always produce a confident answer; this code has explicit uncertain/unavailable/invalid states and tests them | `shared/diagnosis.py`; LoRa status round-trip tests |
| Contract enforcement | Exact sample rate/window/feature order/artifact hash/version; wrong input is rejected, not silently coerced | `bundle.py`; test rejects scikit-learn drift |
| Provenance-aware replay | Separates documented dataset label from model result; marks simulated; license/checksum | `paderborn_replay.py`; dashboard labels |
| End-to-end integration | Same feature contract in training, API, and edge; same event identity across radio/gateway/API | `test_bearing_integration.py` |

What is **not** expensive to reproduce: the Random Forest, the 16 features, the Streamlit UI, the Paderborn data loader, the cost sum. Do not confuse these with a moat.

---

## 5. Assets that could become the center of a different product

### A. The evidence record → **repair verification / closure assurance**
A before/after pair of diagnostic records can prove whether a repair changed the machine's condition. The existing record already carries model version, status, evidence, and confirmation requirement. This is the strongest causal fit.

### B. The durable relay → **offline-first field evidence for remote assets**
The outbox/spool/protocol can carry any compact, typed evidence event, not just bearing diagnoses. This supports products for remote sites, but the domain model would be new.

### C. The contract + refusal policy → **edge AI deployment assurance**
The bundle validator and status taxonomy can become a preflight gate for industrial models: wrong contract, version drift, missing artifact, OOD input → refuse. This is a developer/MLOps product; technically credible, less emotional.

### D. The provenance manifest → **verifiable condition passport**
The manifest proves where a recording came from and under what license. Combined with a signed report, it could support used-equipment handover. But the market already has inspection/condition-report platforms; the sensor evidence is the only differentiator.

### E. The technician feedback loop → **field-calibrated diagnostics**
Feedback is captured but unused. A product could turn confirmations into calibration/active learning. This is a real gap, but requires retraining/calibration data and risks overclaiming in a hackathon.

---

## 6. Assets with no strategic value

- Empty repair-document and pricing catalogs.
- Legacy synthetic telemetry/Isolation Forest (only compatibility value).
- `shared/health.py` simple threshold score.
- Streamlit styling by itself.
- The Paderborn dataset excerpts as a commercial asset (CC-BY-NC-4.0).
- The current "component schematic" as a differentiator; it is presentation, not evidence.

---

## 7. The hidden-asset thesis

**The product should not be "a better bearing model." It should be "a trustworthy way to decide that a physical intervention worked."**

That thesis uses the strongest assets (records, uncertainty, delivery, contracts) and avoids competing on the weakest asset (model accuracy). It also creates a demo that can prove a *decision*, not just display a prediction.
