# 06 — Winning Product Blueprint: AXON Verify

**Product:** AXON Verify  
**Category:** Verified-repair platform / repair closure assurance for industrial vibration  
**One-line pitch:** *A repair isn't done until the machine proves it.*

---

## A. New positioning

### Name
**AXON Verify**

### Memorable pitch
*AXON Verify turns "trust me, it's fixed" into a signed, machine-verified repair record — or refuses to close the work order.*

### Exact target user
- **Primary user:** field technician performing rotating-equipment repairs.
- **Buyer:** maintenance service manager at a small-to-mid industrial service company, or facility reliability lead at a plant with in-house maintenance.
- **Economic beneficiary:** facility owner, OEM warranty administrator, or equipment lessor who bears the cost of repeat repairs.
- **Initial segment:** pumps, motors, fans, and compressors with accessible bearing housings, within the validated 4,096-sample @ 64kHz contract.

### Problem statement
Work orders are marked complete on technician assertion or a quick check. There is often no objective, comparable evidence that the machine's condition actually changed. Failed repairs return as callbacks, repeat downtime, warranty disputes, and unsafe "fixes." Existing vibration tools produce data; CMMS produces paperwork; neither produces a closure decision tied to physical evidence.

### Existing alternative
- Visual inspection and operator judgment
- Periodic vibration-analyst reports
- Continuous-monitoring platforms (Hydro, Augury) — provide data/alerts but not a work-order closure gate with portable signed certificates in this form
- CMMS completion checklists and photos (FleetRabbit, ServiceTitan, UpKeep, Fiix)

### Unique value proposition
**The only repair workflow in scope that can say "not verified" and prove why.** AXON Verify captures before/after evidence across Upload/CSV/REST, MQTT (mTLS), or LoRa; applies a conservative policy; and issues a portable Ed25519-signed certificate that verifies offline. If evidence is uncertain or incomparable, it refuses to certify.

### Core differentiator
A **physical closure gate**: comparability is enforced (asset/component/model/sampling/window/operating context), policy is fail-closed, and certificates are tamper-evident with published keys and offline verification.

### What AXON Verify explicitly does not solve
- Not a full CMMS (scheduling/invoicing/inventory/dispatch)
- Not continuous 24/7 monitoring/alerting platform
- No RUL prediction
- Bearing binary within validated scope only; no race-level diagnosis
- Not a replacement for certified analysts/legal inspectors
- Not a safety certification for all operating conditions (scope stated in certificate)
- No fabricated AI advice

---

## B. The core product loop

1. **Create org/site/asset/component/work order** (multi-tenant)
2. **Capture BEFORE** via upload/CSV/replay/MQTT/LoRa or REST ingest
3. **Perform repair**
4. **Capture AFTER** via same transports
5. **Verify** — comparability + policy engine evaluates before/after
   - `VERIFIED`: issue Ed25519-signed certificate, bind to repair, QR/report, public verifier
   - `NOT_VERIFIED` / `INCONCLUSIVE` / `CANNOT_VERIFY`: refusal with explicit reasons, no certificate
6. **Publish/share** — public verifier at `/verify/{id}`, printable HTML report, offline CLI

---

## C. Architecture (implemented)

| Component | Location | Purpose |
|---|---|---|
| Multi-tenant store | `backend/verify_store.py` | SQLite + org scoping, audit, sessions/API keys, dedup |
| AuthN/Z | `backend/auth.py` | PBKDF2 passwords, signed tokens with nonce/revocation, API keys, RBAC |
| Ingestion | `backend/ingestion.py`, `backend/ingest_service.py` | Transport-neutral ingest, contract validation, model inference, tenant binding |
| MQTT ingest/publisher/provision | `backend/mqtt_ingest.py`, `edge/mqtt_publisher.py`, `scripts/mqtt_provision.py` | mTLS, per-device identity, tenant ACLs, dedup |
| Verification policy | `backend/verification.py` | Comparability, verdict matrix, conservative uncalibrated policy, reasons |
| Certificates | `backend/certificates.py` | Canonical JSON, Ed25519 sign/verify, key resolution, digest normalization |
| Public verification | `backend/certificate_verify.py`, routes | Offline CLI + public API + web verifier |
| API | `backend/verify_routes.py` | REST under `/v1`, public endpoints, stats |
| Webapp | `webapp/` | SPA at `/app`, `verify.html` public verifier |
| Calibration | `backend/calibration.py`, `ml/bearing/calibration.py` | State tracking, policy integration, no fabricated artifacts |
| Reports | `backend/report.py` | Printable HTML certificates/reports |

**Signing:** key from `AXON_SIGNING_KEY` / `AXON_SIGNING_KEY_FILE` / store meta / generated (dev).  
**Calibration:** `confidence_calibrated=false` by default; policy explicitly conservative and disclosed.  
**Tenancy:** every tenant-scoped record has `org_id`; app-level guards enforced.
