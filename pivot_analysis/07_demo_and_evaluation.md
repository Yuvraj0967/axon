# 07 — Demonstration and Evaluation

**Goal:** prove the product thesis, not just show a UI. The judge must see that FixProof can **block a bad repair**, **certify a good one**, **refuse when evidence is insufficient**, and **detect tampering** — using working code and reproducible data.

---

## 1. Demo principle

The core claim is:

> **A repair is not closed because a technician says it is done; it is closed because a comparable post-repair vibration signature proves the fault is resolved — within a stated scope.**

The demo must show the **decision** and the **evidence chain**, not a happy-path dashboard.

### Data honesty up front

The packaged Paderborn excerpts are real recordings, but they are **not a chronologically recorded before/after repair**. The demo will use them to construct clearly labeled repair scenarios:

| Scenario | Before | After | Status | Why it is honest |
|---|---|---|---|---|
| Failed repair | KA04 window 0 | KA04 window 1 | Same damaged recording, two windows | Real signal; no repair occurred; proves the gate catches an unchanged fault signature |
| Successful repair | KA04 window 0 | K003 window 0 | Different physical bearings, same Paderborn test rig and operating condition N09_M07_F10 | Reconstructed replacement scenario; after is a held-out healthy recording; label explicitly |
| Inconclusive | KA04 window 0 | KI04 window 0 | Held-out damaged recording; model returns uncertain | Real held-out failure; proves refusal |
| Model unavailable | KA04 window 0 | any | Bundle disabled | Proves no false certificate |
| Tampered certificate | Successful certificate | edited copy | No new inference | Proves signature/tamper detection |

**Banner in the UI and README:** *“Demo scenarios are reconstructed from real Paderborn recordings. They are not recordings of an actual repair. The model and verdict logic are real; the repair sequence is simulated.”*

Do not claim “we repaired a bearing” or “this is field data.” Do not hide the training/held-out split. The demo’s technical proof is the decision logic and certificate, not a fabricated repair.

### Why this is still a legitimate demo

- The signals are real, licensed, checksummed Paderborn data.
- The model is the packaged model, not a mock.
- The verdict is computed from the signals by the same code path used in production.
- The failed-repair case uses the **same physical recording** before/after, so the “no change” detection is genuine.
- The uncertain case uses a **held-out** damaged recording, showing the model is not perfect.
- The certificate is cryptographically bound to the evidence hashes; tampering is detectable.
- No output is pre-scripted or hardcoded; the judge can change inputs and see the verdict change.

---

## 2. Setup procedure

### Environment

```bash
cd /path/to/axon-feature-edge
python3.11 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt -r edge/requirements.txt -r dashboard/requirements.txt
.venv/bin/pip install cryptography qrcode[pil]   # P0/P1 additions
```

Pinned versions matter: the model bundle requires `scikit-learn==1.9.1`, `numpy==1.26.4`, `joblib==1.6.0`. The system Python 3.14 environment in this audit did not satisfy the model contract. Use the venv.

### Start

```bash
AXON_STORAGE_MODE=memory .venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
BACKEND_URL=http://127.0.0.1:8000 .venv/bin/python -m streamlit run dashboard/app.py --server.port 8501
```

### Seed demo repairs

```bash
.venv/bin/python demo/repairs/seed.py --reset
```

The seed script must:
- Create three repair sessions: `WO-1042` (failed), `WO-1043` (success), `WO-1044` (inconclusive).
- Use only the packaged recordings and the real model.
- Write a `demo/repairs/manifest.json` with source IDs, window indices, checksums, and the disclosure text.
- Be idempotent; `--reset` clears only FixProof demo state.

### Reset

```bash
.venv/bin/python demo/repairs/seed.py --reset
# restart the API to clear MemoryStore
```

Do not delete unrelated test results or user data.

---

## 3. Timed demo (5 minutes)

### 0:00–0:30 — The problem

Show a work order:

> **WO-1042 — Pump 7, drive-end bearing — technician marked “repair complete.”**
> “This is how most maintenance gets closed: someone says it’s fixed. If it isn’t, the machine comes back. We make the machine sign off.”

### 0:30–1:30 — Failed repair is blocked

1. Open Repair `WO-1042`.
2. Capture **before**: KA04 window 0.
   - Status: `FAULT_SUSPECTED`
   - Healthy 0.000 / Damage 1.000
   - Show waveform and evidence.
3. Mark repair complete; capture **after**: KA04 window 1.
   - Status: `FAULT_SUSPECTED`
   - Healthy 0.000 / Damage 1.000
4. Click **Verify repair**.
   - Verdict: **NOT VERIFIED**
   - Reasons: after-repair signature still indicates damage; damage probability did not drop below policy; no certificate.
   - UI: “Do not close this work order.”

**Judge takeaway:** the system refuses a plausible human claim.

### 1:30–2:30 — Successful repair is certified

1. Open `WO-1043`.
2. Before: KA04 window 0 → damage 1.000.
3. After: K003 window 0 (held-out healthy) → healthy 1.000.
4. Verify → **VERIFIED**; certificate issued.
5. Show certificate details: asset, component, work order, technician, model version/hash, input contract, before/after probabilities, policy, comparability, signature, public key ID.
6. Scan QR (P1) or open verification page; show **VALID**.

**Disclosure on screen:** “Reconstructed replacement scenario from two real Paderborn recordings on the same test rig/operating condition; not a recorded repair.”

### 2:30–3:15 — Tamper detection

1. Open a copy of the certificate JSON.
2. Change `verdict` from `VERIFIED` to `NOT_VERIFIED` (or change `asset_id`/`after.probabilities`).
3. Run **Verify certificate** (server or offline CLI).
4. Result: **INVALID — signature mismatch** (or field-level failure).

**Judge takeaway:** the certificate is not a PDF; it is evidence-bound.

### 3:15–4:00 — Refusal / uncertainty

1. Open `WO-1044`.
2. Before: KA04 (damage 1.000).
3. After: KI04 window 0 (held-out damage; model top healthy 0.665, below the 0.70 threshold).
4. Verify → **INCONCLUSIVE**; no certificate; reasons: after status `DIAGNOSIS_UNCERTAIN`; re-capture under comparable conditions or inspect manually.
5. Optionally disable the model bundle and show **CANNOT_VERIFY**; no certificate.

**Judge takeaway:** the system does not turn uncertainty into a pass.

### 4:00–4:30 — Offline durability (if implemented)

1. Stop the API.
2. Capture an edge event; show it queued in the SQLite outbox.
3. Restart the API; retry.
4. Event delivered exactly once; repair session binds the event ID; verification proceeds.

If this is not ready, explain the tested outbox/spool behavior from the baseline and show the test output; do not fake it live.

### 4:30–5:00 — Close

> “FixProof doesn’t predict when a machine will fail. It proves whether a repair worked. The model can refuse, the certificate can be verified offline, and the work order stays open until the machine’s signature changes. That’s the difference between a maintenance log and maintenance proof.”

---

## 4. 90-second core demo

Use only the failed repair + successful repair + tamper:

> “WO-1042 says the bearing was replaced. Before: damage probability 1.0. After: still 1.0. FixProof refuses to close it — no certificate. WO-1043: before 1.0, after healthy 1.0. It issues a signed certificate bound to the model version and both evidence hashes. Scan it: valid. Change one field: invalid. A repair isn’t done until the machine proves it.”

This is the version for a 90-second pitch or a crowded demo floor.

---

## 5. Evidence displayed to judges

| Evidence | Where | Why it matters |
|---|---|---|
| Before/after waveforms | Repair workspace | Shows the physical input, not a text claim |
| Probabilities + status | Before/after cards | Shows the model output and uncertainty |
| Model version, artifact hash, input contract | Certificate/“Why” panel | Proves which model and data contract produced the decision |
| Comparability checks | Verdict panel | Shows the system refuses non-comparable captures |
| Policy version/thresholds | Verdict panel | Shows the verdict is rule-based, not arbitrary |
| Certificate JSON + signature | Certificate panel | Portable evidence artifact |
| Public key + verifier result | Verification page/CLI | Independent verification |
| `pytest` output | Terminal/slide | Shows negative cases are tested |
| Dataset manifest/license | “Data provenance” panel | Shows real, attributable data and its limits |

### Measurable before/after

| Scenario | Before damage | After damage | Verdict |
|---|---:|---:|---|
| Failed repair | 1.000 | 1.000 | NOT_VERIFIED |
| Successful repair | 1.000 | 0.000 (healthy 1.000) | VERIFIED |
| Uncertain held-out | 1.000 | 0.335 (top healthy 0.665) | INCONCLUSIVE |
| Model unavailable | 1.000 | n/a | CANNOT_VERIFY |

These are **uncalibrated model outputs**, not field accuracy. Display the calibration disclaimer. Do not claim “100% confidence” as a truth claim; call it “model probability 1.000 on this window.”

---

## 6. Test scenarios (minimum five)

### T1 — Failed repair is blocked

- Before: KA04 w0; after: KA04 w1.
- Expected: `NOT_VERIFIED`; no certificate; reason includes unchanged damage signature.
- Assert: certificate endpoint returns 404/409; repair status remains open.

### T2 — Successful repair is certified

- Before: KA04 w0; after: K003 w0.
- Expected: `VERIFIED`; certificate exists; signature verifies; verdict recomputed.
- Assert: certificate `before.event_id`/`after.event_id` match stored diagnostics; `model_version` matches bundle.

### T3 — Uncertain held-out case is refused

- Before: KA04 w0; after: KI04 w0.
- Expected: `INCONCLUSIVE`; no certificate; reason includes `DIAGNOSIS_UNCERTAIN`.
- Assert: the system never maps top-1 healthy at 0.665 to `VERIFIED` merely because it is the argmax.

### T4 — Model unavailable

- Disable/misconfigure the bundle.
- Expected: `CANNOT_VERIFY`; no certificate; explicit reason.
- Assert: no fallback to a hardcoded “healthy.”

### T5 — Tampered certificate

- Take T2 certificate; mutate verdict/asset/probabilities/signature.
- Expected: verification fails with a specific reason.
- Assert: every signed field mutation is detected; wrong public key fails; malformed JSON fails.

### T6 — Invalid/non-comparable input

- After window has 2,048 samples or wrong sampling rate; or operating_condition_id differs.
- Expected: `SENSOR_DATA_INVALID` or `INCONCLUSIVE`; no certificate.
- Assert: the model contract rejects before inference; no partial result.

### T7 — Offline durability / idempotency

- Stop API; capture an edge event; confirm outbox retains it; restart; retry.
- Expected: exactly one API event; repair binds; duplicate retry does not create a second event.
- Assert: gateway spool/dedupe behavior from `test_lora_protocol.py` still passes.

### T8 — Before is healthy

- Before K003; after K003.
- Expected: `NOT_APPLICABLE` (“no fault to verify”), no certificate.
- Assert: the system does not issue a repair certificate for a machine that was already healthy.

---

## 7. Automated evaluation plan

### Unit / component

- Verdict matrix (all rows in the policy table).
- Comparability matrix (asset/component/model/rate/window/condition/time).
- Certificate canonicalization, sign/verify, field-by-field tamper.
- Feature delta computation.

### Integration

- Packaged windows → repair session → verdict → certificate → verify.
- Loopback edge event → event_id binding → repair.
- API error paths.

### Regression

- Existing 33 tests must remain green.
- The new tests must not depend on network/Influx/Postgres.
- `AXON_STORAGE_MODE=memory` default for tests.

### Demo reproducibility

- `seed.py --reset` twice produces the same scenario IDs/verdicts (timestamps may differ).
- A clean checkout + `README` commands reaches the demo in ≤10 minutes.
- The demo works with no internet.

### Evaluation metrics for the product claim (not model accuracy)

- **False-certification rate:** number of failed/uncertain repairs that receive `VERIFIED` (target: 0 in the test matrix).
- **Refusal coverage:** every non-comparable/unavailable case returns a non-certificate verdict (target: 100%).
- **Tamper detection:** every signed-field mutation is rejected (target: 100%).
- **Time to verdict:** local inference + policy < 2 seconds on the demo host (target).
- **Capture completeness:** each repair has before/after evidence and a model version (target: 100%).

Do not report model accuracy as product accuracy.

---

## 8. Fallback plan

| Failure | Fallback |
|---|---|
| Streamlit won’t start | Use FastAPI `/docs` + `curl` to run the same endpoints; show certificate CLI |
| Model bundle won’t load | Run the `CANNOT_VERIFY` scenario; explain the refusal path is the product; use a pre-generated certificate from a known-good run for the verification demo |
| Demo data missing | Use `demo/paderborn` files and the manifest; verify checksums |
| Network/API down | Use loopback/offline scenario; show outbox/spool evidence |
| Certificate key missing | Pre-generate a key pair in the demo env; do not commit the private key; show public key + verifier |
| Live demo fails completely | Play the recorded 90-second video; keep the terminal/test output visible; offer a code walkthrough |

**Do not** switch to a fake “everything passed” screen. A clean failure with a clear explanation is more credible than a staged success.

---

## 9. Technical proof that distinguishes FixProof from a superficial prototype

A superficial prototype can show two waveforms and a green badge. FixProof must prove:

1. **The verdict is computed, not selected.** Change the after window; the verdict changes.
2. **The system can refuse.** A failed repair and an uncertain case produce different non-success verdicts.
3. **The certificate is bound to evidence.** Mutating any signed field breaks verification.
4. **The model contract is enforced.** Wrong sample rate/window is rejected before inference.
5. **The evidence survives intermittency.** Outbox/gateway behavior is tested, not narrated.
6. **The negative cases are tested.** The test suite asserts no certificate for failed/uncertain/unavailable cases.
7. **The data is disclosed.** The judge can see the Paderborn source, license, window indices, and the “reconstructed scenario” banner.

If any of these is missing, the demo is weaker and the score should be adjusted.

---

## 10. What not to do in the demo

- Do not claim the model is calibrated or field-validated.
- Do not claim the reconstructed pairs are a real repair.
- Do not claim the certificate is legally binding.
- Do not claim the model detects all bearing faults or localizes race defects.
- Do not show a “100% confidence” badge without the uncalibrated disclaimer.
- Do not hide the held-out KI04 uncertainty; it is the best evidence of honesty.
- Do not rely on internet access, Docker, or hardware.
- Do not use a pre-recorded “success” if the live code can produce it; use the recording only as fallback.
