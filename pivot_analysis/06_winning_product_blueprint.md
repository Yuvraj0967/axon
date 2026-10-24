# 06 — Winning Product Blueprint: FixProof

**Product:** FixProof  
**Category:** Repair verification / maintenance closure assurance  
**One-line pitch:** *A repair isn't done until the machine proves it.*

---

## A. New positioning

### Name
**FixProof**

### Memorable pitch
*FixProof turns "trust me, it's fixed" into a signed, machine-verified repair record — or refuses to close the work order.*

### Exact target user
- **Primary user:** field technician performing bearing/rotating-equipment repairs.
- **Buyer:** maintenance service manager at a small-to-mid industrial service company, or facility reliability lead at a plant with in-house maintenance.
- **Economic beneficiary:** facility owner, OEM warranty administrator, or equipment lessor who bears the cost of repeat repairs.
- **Initial segment:** pumps, motors, fans, and compressors with accessible bearing housings, where a 4,096-sample vibration capture is practical.

### Problem statement
A work order is marked "complete" when a technician believes the repair is done. There is often no objective, comparable evidence that the machine's condition actually changed. Failed repairs return as callbacks, repeat downtime, warranty disputes, and unsafe "fixes." Existing vibration tools produce data; CMMS produces paperwork; neither produces a **closure decision** tied to physical evidence.

### Existing alternative
- Visual inspection and operator judgment ("it sounds better").
- Periodic vibration-analyst reports, often days later.
- Continuous-monitoring platforms (Hydro, Augury) that provide data/alerts but not a work-order closure gate.
- CMMS completion checklists and photos (FleetRabbit, ServiceTitan, UpKeep, Fiix).
- Waiting for the machine to fail again.

### Unique value proposition
**The only repair workflow that can say "not verified" and prove why.** FixProof captures before/after vibration evidence, applies a conservative model verdict within a validated scope, and issues a portable certificate that verifies offline. If the evidence is uncertain or incomparable, it refuses to certify.

### Core differentiator
A **physical closure gate**: the system does not accept "repair complete" as an input; it requires a post-repair signature that is comparable to the pre-repair signature, and it can block closure.

### Product category
Repair verification / maintenance closure assurance — adjacent to condition monitoring and CMMS, but not either one.

### Why now
- Edge inference is cheap enough to run locally, without cloud dependence.
- Maintenance labor is scarce; callbacks/rework are expensive.
- Condition-monitoring hardware is commoditizing; the workflow/trust layer is the remaining gap.
- Warranty/insurance scrutiny rewards evidence.
- AI hype has created skepticism; a product that can **refuse** and **prove** is differentiated.

### What FixProof explicitly does not solve
- It is not a full CMMS (scheduling, invoicing, inventory, dispatch).
- It is not continuous monitoring or a 24/7 alerting platform.
- It does not predict remaining useful life.
- It does not diagnose every fault type; initial scope is bearing/rotating-equipment vibration within the validated model contract.
- It does not replace a certified vibration analyst or a legal inspector.
- It does not certify a repair as safe for all operating conditions; the certificate states its scope.
- It does not use an LLM to invent repair advice.

---

## B. The core product loop

```mermaid
sequenceDiagram
    actor Tech as Technician
    participant UI as FixProof UI
    participant API as FastAPI
    participant Model as Bearing Bundle
    participant Store as Repair Store
    participant Sign as Ed25519 Signer
    participant Verifier as Certificate Verifier

    Tech->>UI: Open work order WO-1042
    UI->>API: POST /repairs
    API->>Store: create repair session
    Tech->>UI: Capture BEFORE vibration
    UI->>API: POST /repairs/{id}/capture (phase=before)
    API->>Model: validate contract + probabilities
    Model-->>API: healthy/damage + confidence
    API->>Store: bind before diagnostic
    Tech->>UI: Perform repair, mark ready
    Tech->>UI: Capture AFTER vibration
    UI->>API: POST /repairs/{id}/capture (phase=after)
    API->>Model: validate contract + probabilities
    Model-->>API: healthy/damage + confidence
    API->>Store: bind after diagnostic
    Tech->>UI: Verify repair
    UI->>API: POST /repairs/{id}/verify
    API->>Store: load before/after + metadata
    API->>API: comparability + verdict policy
    alt VERIFIED
        API->>Sign: canonicalize + sign certificate
        Sign-->>API: signature
        API->>Store: persist certificate
        API-->>UI: VERIFIED + certificate + QR
    else NOT VERIFIED / INCONCLUSIVE
        API-->>UI: refusal + reasons; no certificate
    end
    Verifier->>API: POST /certificates/verify (or offline CLI)
    API-->>Verifier: valid / invalid + reason
```

### Initiation
A work order is opened manually in FixProof (P0) or imported from a CMMS via CSV/API (P1).

### Data/context entering
- Asset ID, component ID, work-order ID, technician ID.
- Operating-condition key (speed/load/configuration) or a Paderborn experiment ID for the demo.
- Before and after vibration windows (4,096 samples @ 64 kHz) or references to diagnostic events.
- Model bundle identity and input contract.

### Processing
1. Validate both windows against the model contract.
2. Run the model; store diagnostics with status/confidence/probabilities/features.
3. Check comparability: same asset/component, same model version, same sampling rate/window, same operating-condition key; timestamps ordered.
4. Apply the verdict policy (below).
5. If `VERIFIED`, canonicalize the evidence and sign a certificate.
6. If not, persist the refusal with explicit reasons.

### Action/outcome
- `VERIFIED`: certificate issued; UI shows "Ready to close" (the CMMS closure remains an external action in P0).
- `NOT VERIFIED`: UI shows "Do not close"; reasons and next steps.
- `INCONCLUSIVE` / `CANNOT_VERIFY`: UI shows "Cannot verify"; no certificate; re-capture or inspect.

### How the user verifies
- In-app "Why this verdict" panel: before/after probabilities, feature deltas, comparability, model version/hash, policy version.
- Certificate page with QR code and public key.
- Offline CLI verifier: `python -m backend.certificate_verify certificate.json --public-key public.pem`.

### Uncertainty/failure behavior
The product is designed to **fail closed**:
- Model unavailable → `CANNOT_VERIFY`; no certificate.
- Sensor data invalid → `INCONCLUSIVE`; no certificate.
- Before uncertain → `INCONCLUSIVE`; cannot establish a fault to resolve.
- Conditions incomparable → `INCONCLUSIVE`; no false credit.
- Signature key unavailable → 503; no unsigned certificate.
- Network offline → edge outbox/gateway spool retains evidence; verification waits.

### Value without the advanced AI
If the model is unavailable, the system can still show the before/after waveforms and deterministic feature deltas (RMS, kurtosis, band energy) and a **comparability report**. It cannot issue a model-backed certificate; it says so. This keeps the workflow useful and honest, rather than pretending the AI is essential.

---

## C. Architecture mapped to the repository

### Existing components to reuse unchanged

| File/function | Role in FixProof |
|---|---|
| `ml/bearing/signal.py:validate_signal, engineered_features, feature_vector` | Contract validation and 16-feature evidence |
| `ml/bearing/bundle.py:load_bearing_bundle, probabilities` | Model identity, hash, input contract, inference |
| `ml/bearing/taxonomy.py` | Fault classes/locations |
| `shared/diagnosis.py:diagnosis_from_probabilities, unavailable_diagnosis` | Status/uncertainty record |
| `shared/lora_protocol.py` | Edge delivery of diagnostic summaries (no wire change in P0) |
| `edge/lora_transport.py`, `edge/lora_gateway.py` | Durable offline evidence delivery |
| `edge/bearing_inference.py` | Edge inference wrapper |
| `backend/paderborn_replay.py` | Deterministic demo windows/provenance |
| `dashboard/app.py` CSS/helpers | Reuse styling and honest uncertainty display |

### Files to modify

| File | Change |
|---|---|
| `backend/main.py` | Add repair Pydantic models, routes, store methods, certificate endpoints; keep existing diagnostic routes |
| `dashboard/app.py` | Add "Repair verification" workspace; keep "Bearing diagnosis" as secondary "Evidence explorer" |
| `edge/bearing_runner.py` | Optional `--repair-id`/`--phase` metadata; P0 can skip by binding event IDs in API |
| `backend/README.md`, `README.md` | Document new workflow and demo commands |

### New modules

| Module | Purpose |
|---|---|
| `backend/repair_verification.py` | Verdict policy, comparability, reasons, feature deltas |
| `backend/certificates.py` | Canonical JSON, Ed25519 sign/verify, key loading, certificate schema |
| `backend/repair_store.py` | Repair/certificate persistence for MemoryStore and ExternalStore |
| `backend/certificate_verify.py` | Offline CLI verifier |
| `demo/repairs/seed.py` | Deterministic demo repair sessions/scenarios |
| `demo/repairs/README.md` | Provenance and "reconstructed scenario" disclosure |
| `tests/test_repair_verification.py` | Verdict matrix |
| `tests/test_certificates.py` | Sign/verify/tamper |
| `tests/test_repair_api.py` | API/contract/idempotency |
| `tests/test_repair_integration.py` | Packaged windows + loopback + certificate |

### Data contracts

```python
class RepairCreate(BaseModel):
    asset_id: str
    component_id: str
    work_order_id: str
    technician_id: str
    operating_condition_id: str

class RepairCapture(BaseModel):
    phase: Literal["before", "after"]
    recording_id: str | None = None   # demo/replay path
    window_index: int | None = None
    event_id: str | None = None       # production edge path
    captured_at: datetime | None = None

class RepairVerdict(BaseModel):
    repair_id: str
    verdict: Literal["VERIFIED", "NOT_VERIFIED", "INCONCLUSIVE", "CANNOT_VERIFY", "NOT_APPLICABLE"]
    reasons: list[str]
    before: dict
    after: dict
    comparability: dict
    certificate: dict | None
```

### API

| Method | Path | Purpose |
|---|---|---|
| POST | `/repairs` | Create repair session |
| GET | `/repairs/{repair_id}` | Session state + evidence |
| GET | `/repairs?asset_id=` | List sessions |
| POST | `/repairs/{repair_id}/capture` | Bind before/after diagnostic (replay or event_id) |
| POST | `/repairs/{repair_id}/verify` | Compute verdict; issue certificate if verified |
| GET | `/repairs/{repair_id}/certificate` | Certificate JSON |
| GET | `/repairs/{repair_id}/certificate/qr` | QR PNG (P1) |
| POST | `/certificates/verify` | Verify certificate JSON |
| GET | `/certificates/public-key` | Ed25519 public key + key ID |
| GET | `/healthz` | Liveness (optional) |

### Database changes

For the hackathon, use the in-memory store by default and optionally Postgres. No migration framework exists; add an explicit idempotent schema bootstrap.

```sql
CREATE TABLE IF NOT EXISTS repair_sessions (
  repair_id TEXT PRIMARY KEY,
  asset_id TEXT NOT NULL,
  component_id TEXT NOT NULL,
  work_order_id TEXT NOT NULL,
  technician_id TEXT NOT NULL,
  operating_condition_id TEXT NOT NULL,
  status TEXT NOT NULL,
  before_event_id TEXT,
  after_event_id TEXT,
  verdict TEXT,
  certificate_id TEXT,
  created_at TIMESTAMPTZ NOT NULL,
  verified_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS repair_certificates (
  certificate_id TEXT PRIMARY KEY,
  repair_id TEXT NOT NULL,
  payload JSONB NOT NULL,
  signature TEXT NOT NULL,
  public_key_id TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL
);
```

### Certificate schema (canonical JSON)

```json
{
  "certificate_version": "fixproof-cert-v1",
  "certificate_id": "uuid",
  "repair_id": "uuid",
  "asset_id": "demo-rig-01",
  "component_id": "bearing-drive-end",
  "work_order_id": "WO-1042",
  "technician_id": "tech-7",
  "verdict": "VERIFIED",
  "scope": "Bearing vibration screening within the validated model contract; not a legal certification.",
  "policy": {
    "policy_version": "fixproof-policy-v1",
    "minimum_confidence": 0.70,
    "minimum_damage_probability_drop": 0.30,
    "maximum_after_damage_probability": 0.30
  },
  "before": {
    "event_id": "...",
    "captured_at": "...",
    "status": "FAULT_SUSPECTED",
    "fault_class": "other_bearing_damage",
    "confidence": 1.0,
    "probabilities": {"healthy": 0.0, "other_bearing_damage": 1.0},
    "features_sha256": "...",
    "evidence_sha256": "...",
    "model_version": "axon-bearing-rf-ef4473b3cee7",
    "input_contract": {"sampling_frequency_hz": 64000, "window_samples": 4096}
  },
  "after": { "...": "same shape" },
  "comparability": {
    "same_asset": true,
    "same_component": true,
    "same_model": true,
    "same_sampling_rate": true,
    "same_window": true,
    "same_operating_condition": true
  },
  "issued_at": "...",
  "issuer": "FixProof",
  "public_key_id": "fixproof-key-1",
  "disclaimer": "Tamper-evident evidence record, not a legal certification or a guarantee of future operation."
}
```

**Signature:** Ed25519 over `SHA-256(canonical_json)` or directly over canonical bytes; document the exact convention. Include the public key ID in the payload. The verifier must reject unknown key IDs.

### Verdict policy (P0)

| Before status | After status | Comparability | Verdict |
|---|---|---|---|
| `FAULT_SUSPECTED` | `HEALTHY_WITHIN_VALIDATED_SCOPE` + confidence ≥ 0.70 + damage drop ≥ 0.30 | all true | `VERIFIED` |
| `FAULT_SUSPECTED` | `FAULT_SUSPECTED` | all true | `NOT_VERIFIED` |
| `FAULT_SUSPECTED` | `DIAGNOSIS_UNCERTAIN` | all true | `INCONCLUSIVE` |
| `FAULT_SUSPECTED` | `MODEL_UNAVAILABLE` / `SENSOR_DATA_INVALID` | any | `CANNOT_VERIFY` / `INCONCLUSIVE` |
| `DIAGNOSIS_UNCERTAIN` | any | any | `INCONCLUSIVE` (no baseline fault) |
| `HEALTHY_WITHIN_VALIDATED_SCOPE` | any | any | `NOT_APPLICABLE` (no fault to verify) |
| any | any | false | `INCONCLUSIVE` |
| after timestamp ≤ before timestamp | any | any | `INCONCLUSIVE` / validation error |

The thresholds are configurable and must be labeled as policy, not calibrated truth. The model's probabilities are uncalibrated; the UI must say so.

### Security boundaries

- Private signing key in env/file outside the repo; never committed.
- Public key endpoint; key ID in certificate.
- Server recomputes the verdict; never trusts a client-supplied verdict.
- Write endpoints protected by a simple API key for the demo; document that this is not production auth.
- Technician ID is an opaque identifier; no PII.
- Certificate is tamper-evident, not a legal certification.
- No raw customer data in logs beyond IDs/hashes.

### Failure handling

| Failure | Behavior |
|---|---|
| Model bundle missing/invalid | `CANNOT_VERIFY`, no certificate, 503 detail |
| Wrong sample rate/window | `SENSOR_DATA_INVALID`, no certificate |
| Before/after conditions differ | `INCONCLUSIVE`, reason |
| Duplicate capture | Idempotent by event_id/phase; reject conflicting overwrite |
| DB unavailable | 503; edge outbox/spool retains |
| Signing key missing | 503; never issue unsigned certificate |
| Certificate tampered | Verifier returns invalid with field-level reason |
| Network offline | Edge event queued; API later binds event_id |

### Evaluation/testing requirements

- Unit tests for every verdict row.
- Certificate tamper tests for every signed field.
- API tests for missing sessions, wrong phase, duplicate capture, unauthorized write.
- Integration test: packaged windows → repair session → verdict → certificate → verify.
- Integration test: loopback edge event → event_id bound to repair.
- Negative test: uncertain KI04 window does not produce `VERIFIED`.
- Negative test: model unavailable does not produce a certificate.
- Demo script test: reset/seed/replay deterministic.

---

## D. Scope control

### P0 — essential to prove the thesis

1. Repair session create/get/list.
2. Capture before/after from packaged Paderborn recordings (replay path).
3. Verdict engine with `VERIFIED`, `NOT_VERIFIED`, `INCONCLUSIVE`, `CANNOT_VERIFY`, `NOT_APPLICABLE`.
4. Comparability checks (asset/component/model/rate/window/condition/timestamp).
5. Ed25519 certificate issue + verify endpoint + offline CLI.
6. Dashboard "Repair verification" screen with verdict, reasons, before/after evidence, certificate.
7. Deterministic seed script with failed/successful/uncertain scenarios and explicit provenance labels.
8. Tests: verdict matrix, certificate tamper, API, integration.
9. Demo reset + fallback video.

### P1 — high-value if time permits

- QR code + printable certificate.
- Work-order CSV import/export.
- Technician confirmation/approval role.
- Feature-delta visualization/overlay.
- Offline edge capture binding via `--repair-id`/`--phase`.
- Audit timeline (capture → repair → verify → certificate).
- Public verification page (read-only).
- Basic API-key auth.

### P2 — post-hackathon

- CMMS integrations (ServiceTitan, UpKeep, Fiix, Maximo).
- Real hardware capture kit and sensor onboarding.
- Multiple components/assets per work order.
- Calibration/conformal thresholds using field data.
- Multi-tenant auth/RBAC.
- Warranty/insurance partner APIs.
- Mobile capture app.
- Signed device identity/attestation.

### Explicit exclusions

Do **not** build during the hackathon:
- A full CMMS (scheduling, invoicing, inventory).
- A continuous-monitoring/alerting platform.
- Remaining-useful-life prediction.
- A general-purpose LLM chatbot or repair-advice generator.
- A new ML model or synthetic training pipeline.
- A blockchain/token.
- A marketplace.
- A legal certification claim.
- Hardware acquisition unless already available and validated.

---

## E. Why this is not just a dashboard

A dashboard displays a prediction. FixProof:

1. **Changes a decision** — it can block work-order closure.
2. **Requires two evidence states** — before and after, not one prediction.
3. **Refuses** — uncertain/incomparable/unavailable cases do not get a certificate.
4. **Binds evidence to identity** — asset, component, model version, contract, timestamps.
5. **Produces a portable artifact** — a signed certificate that verifies offline and fails on tampering.
6. **Works under intermittency** — the durable edge path is part of the product, not a demo detail.

That combination is the product. The model is a component; the closure decision and evidence chain are the value.
