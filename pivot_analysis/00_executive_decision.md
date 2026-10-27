# 00 — Executive Decision

**Repository audited:** `/home/pulkithanda/Downloads/axon-feature-edge(2)/axon-feature-edge`  
**Decision date:** 2026-10-24  
**Decision:** **Pivot to AXON Verify** — tamper-evident repair verification with tenant-scoped ingestion across Upload/CSV/REST, MQTT (mTLS), and LoRa; a conservative verification policy; and Ed25519-signed certificates with public offline verification.

---

## The decision in one paragraph

The codebase is a well-engineered **bearing-diagnosis demo**, but its strongest asset is not the classifier — it is the **auditable decision pipeline**: strict input/model contracts, uncertainty/refusal states, durable offline delivery, provenance, and transport hardening. AXON Verify repurposes those assets into a **verified-repair platform** for industrial vibration/maintenance service companies. A repair is only closed with objective before/after evidence; if evidence is incomparable, uncertain, or the repair does not resolve the fault under policy, the system refuses to certify and explains why. Certificates are canonical JSON signed with Ed25519 and verifiable offline with published keys. The system is multi-tenant, supports MQTT with per-device mTLS and tenant-scoped ACLs, and exposes a vanilla JS/HTML/CSS webapp at `/app` plus a public verifier at `/verify/{id}`. No market metrics are fabricated; uncertainty, calibration status, and reconstructed/demo data are explicitly disclosed.

---

## 1. What is the product today, based on the code?

**AXON Verify** (implemented):

- **Model scope:** binary bearing classification (`healthy` vs `other_bearing_damage`) using the packaged Random Forest from `ml/artifacts/bearing/active/`. Classes unchanged.
- **Three transports:** Upload/CSV/REST ingestion, MQTT ingest with per-device mTLS and tenant ACLs (`edge/mqtt_publisher.py`, `backend/mqtt_ingest.py`, `scripts/mqtt_provision.py`), and LoRa via existing gateway path.
- **Verification workflow:** work orders → before/after captures → comparability checks (asset/component/model/sampling/window/operating context) → policy engine (`backend/verification.py`) producing `VERIFIED` / `NOT_VERIFIED` / `INCONCLUSIVE` / `CANNOT_VERIFY` with explicit reasons.
- **Certificates:** canonical JSON + Ed25519 signatures (`backend/certificates.py`), QR codes, printable HTML reports (`backend/report.py`), public verification (`/v1/public/certificates/{id}`, `/verify/{id}`), offline CLI (`backend/certificate_verify.py`). Cross-language parity verified.
- **Multi-tenant storage:** SQLite-backed `VerifyStore` with `org_id` on tenant tables, app-level tenant guard, audit log, sessions/API keys. Postgres RLS documented as production path.
- **Auth:** PBKDF2-HMAC-SHA256 passwords (configurable iterations, test override), HMAC-signed session tokens with nonce/revocation, API keys, roles `owner/admin/manager/technician/viewer/customer/api_key` with permission sets.
- **Webapp:** no-build SPA at `/app` (vanilla JS/HTML/CSS), public verifier at `/verify/{id}`, API at `/v1/*`. Legacy Streamlit dashboard remains for compatibility but is not the product path.
- **Calibration:** `ml/bearing/calibration.py` machinery exists; shipped with `confidence_calibrated=false` and conservative policy until a real calibrated artifact exists. No calibration values are fabricated.
- **Tests:** 98 tests passing (including auth, verification policy, certificates, workflow, MQTT topics, calibration).
- **Git:** initialized on `feature/axon-verify` with baseline `be30cc1`.

---

## 2. What is the biggest weakness in its current positioning?

- **Calibration:** probabilities are uncalibrated; policy is intentionally stricter and disclosed.
- **Model scope:** only bearing binary within validated contract; no race-level diagnosis, RUL prediction, or broad fault coverage.
- **Demo data:** Paderborn windows are real but used as reconstructed scenarios (not recorded before/after repairs); explicitly disclosed.
- **Production hardening:** SQLite is fine for demo/self-host; Postgres+RLS recommended for production. No hardware validation performed.
- **Market evidence:** no customer/WTP data fabricated — facts/hypotheses/unknowns labeled honestly.
