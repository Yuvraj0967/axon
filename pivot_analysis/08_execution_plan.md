# 08 — Hackathon Execution Plan

**Assumption:** 36 hours of build time, 3 people (the repo already contains Person 1/2/3 kickoff docs). If solo, use the same order and cut P1 ruthlessly. If the actual event is 24 or 48 hours, scale the milestone windows proportionally; the critical path does not change.

**Baseline:** 33 tests pass in a Python 3.11 venv with pinned requirements. The API, dashboard, and loopback edge path run. The repo is **not** a Git repository. Do not start by rewriting the model; start by preserving the baseline and building the closure workflow.

---

## 0. Non-negotiable constraints

- Do not modify application code until the team accepts the pivot.
- Do not commit signing private keys, real customer data, or the Paderborn raw dataset.
- Do not claim production readiness, calibration, legal certification, or field accuracy.
- Do not remove existing tests or weaken the model contract to make the demo easier.
- Do not replace real inference with a hardcoded verdict; the demo must exercise the model and verdict engine.
- Keep the existing bearing diagnostic path working; FixProof is an additional workflow, not a deletion of the old one.

---

## 1. Milestones

| Milestone | Time | Owner(s) | Depends on | Deliverable | Acceptance criteria |
|---|---:|---|---|---|---|
| **M0 — Baseline + branch** | 0–2h | A | — | Reproducible env; baseline tests; Git baseline; demo skeleton | `pytest` green; API/dashboard start; branch/commit or preserved copy; README commands |
| **M1 — Repair domain + API** | 2–8h | A | M0 | `repair_sessions` model/store/routes | Create/get/list; capture before/after; validation; API tests |
| **M2 — Verdict engine** | 8–14h | A + B | M1 | `repair_verification.py` + policy | Failed/success/uncertain/unavailable/invalid matrix passes; reasons deterministic |
| **M3 — Certificate** | 14–20h | A | M2 | Canonical JSON + Ed25519 sign/verify + CLI | Tamper every signed field fails; valid cert verifies offline; key not in repo |
| **M4 — Dashboard + demo data** | 20–26h | B | M1, M2, M3 | Repair workspace; seed script; provenance banner | Full loop clickable; failed/success/inconclusive scenarios; reset works |
| **M5 — Negative + offline** | 26–30h | A + B | M4 | Tamper, model-unavailable, invalid, offline tests | 5+ scenarios automated; no certificate on any negative case |
| **M6 — Pitch + rehearsal** | 30–34h | C + all | M4, M5 | 90s/2min/5min scripts; Q&A; fallback video | Timed rehearsal under 5:00; projector/terminal test; backup works |
| **M7 — Freeze + final QA** | 34–36h | All | M6 | Final checklist; clean run; submission | Clean checkout → demo in ≤10 min; known issues documented |

### M0 detail

1. Copy the existing tree to a baseline backup (no Git means no undo).
2. `git init` only if the team agrees; otherwise create `baseline/` outside the working tree. The brief asks for a dedicated branch once authorized, but there is no repository yet.
3. Create `.venv` with Python 3.11; install pinned requirements plus `cryptography` and `qrcode[pil]`.
4. Run `AXON_STORAGE_MODE=memory .venv/bin/python -m pytest -q`; save output to `test-results/baseline.txt`.
5. Start API + dashboard; verify `/ready`, `/diagnostics/model-status`, Paderborn catalog; run loopback.
6. Write `demo/repairs/README.md` with provenance/disclosure before building UI.

### M1 detail

- Add Pydantic models and store methods first; keep them independent of the verdict engine.
- Use `event_id` binding: a repair capture can reference an existing diagnostic event or a replay window.
- Do not change the LoRa wire format in P0; bind repair metadata at the API layer.
- Acceptance: create a session, capture before/after from packaged windows, retrieve it; duplicate capture is idempotent.

### M2 detail

- Implement the policy table exactly as documented in `06_winning_product_blueprint.md`.
- Return machine-readable reasons (`AFTER_STILL_FAULT`, `AFTER_UNCERTAIN`, `MODEL_UNAVAILABLE`, `NON_COMPARABLE`, `BEFORE_HEALTHY`, `NO_SIGNATURE_CHANGE`).
- Never let the caller supply the verdict.
- Acceptance: every row of the matrix has a unit test.

### M3 detail

- Use `cryptography.hazmat.primitives.asymmetric.ed25519` (add `cryptography` to requirements) or `pynacl`; either is fine.
- Canonical JSON: sorted keys, compact separators, UTF-8; document the exact bytes signed.
- Private key: env var or file outside the repo; public key endpoint; key ID.
- Include the policy version, model version, artifact hash, and evidence hashes.
- Offline verifier CLI must not need the API or database.
- Acceptance: sign/verify; mutate each field; wrong key; malformed JSON; unknown key ID.

### M4 detail

- New sidebar item **Repair verification**; keep **Bearing diagnosis** as **Evidence explorer**.
- Three seeded sessions with visible scenario labels.
- Show before/after probabilities, status, waveform, feature delta, comparability, policy.
- Certificate panel: JSON download, signature, public key, QR (P1).
- Acceptance: a non-technical person can complete the failed/success loop without terminal commands.

### M5 detail

- Add tamper test that changes `verdict`, `asset_id`, `before.probabilities`, `after.status`, `signature`.
- Add model-unavailable test by pointing the bundle loader at a missing path.
- Add invalid input test (wrong length/rate).
- Add offline/idempotency test using the existing loopback/outbox.
- Acceptance: no negative case produces `VERIFIED` or a certificate.

### M6 detail

- Write the 90-second and 2-minute scripts in `09_pitch_and_judge_defense.md` into cue cards.
- Rehearse with a timer; the live demo must finish under 5:00 with setup already done.
- Record a screen capture of the successful run as fallback.
- Prepare a one-page judge handout with the architecture and evidence.
- Acceptance: two clean rehearsals; fallback plays; Q&A answers are evidence-based.

### M7 detail

- Freeze features; no new UI.
- Run the full test suite, the demo script, and a clean reset.
- Check no private key or large raw data is committed.
- Prepare the final submission text and repository link.
- Acceptance: clean environment run succeeds; known issues listed.

---

## 2. Workstreams (3 people)

| Workstream | Owner | Scope | Integration boundary |
|---|---|---|---|
| **Backend / verdict / certificate** | Person A | M1–M3, M5 backend | Publishes API contracts and test fixtures; does not edit dashboard except contract changes |
| **Dashboard / demo data / UX** | Person B | M4, demo seed, certificate panel, QR | Consumes API only; no direct store access; uses fixed fixture IDs |
| **Pitch / QA / integration** | Person C | M6, test scenarios, fallback, judge Q&A, timing | Owns the demo script; runs end-to-end; does not change backend logic without A |

### Integration contracts (define at hour 2)

- `POST /repairs` request/response JSON.
- `POST /repairs/{id}/capture` request/response; `phase` ∈ {before, after}.
- `POST /repairs/{id}/verify` response with `verdict`, `reasons`, `certificate`.
- Certificate field names/order; canonicalization rule; public key endpoint.
- Demo session IDs: `WO-1042` failed, `WO-1043` success, `WO-1044` inconclusive.

Freeze these by hour 8. UI and backend can then work in parallel.

---

## 3. Critical path

```text
Baseline (M0)
  → Repair session/API (M1)
    → Verdict policy (M2)
      → Certificate (M3)
        → Dashboard integration (M4)
          → Negative/offline tests (M5)
            → Rehearsal (M6)
              → Freeze (M7)
```

The **certificate** is the long pole: it depends on stable verdict output and canonical evidence. Do not start with the QR code or fancy UI.

### If time slips

Cut in this order:

1. QR code / printable certificate.
2. Work-order CSV import.
3. Offline CLI verifier (keep server verification).
4. Feature-delta visualization.
5. Non-comparable operating-condition gate (keep asset/model/rate/window checks).
6. Offline edge binding (show the baseline tests instead).
7. Multi-role approval.

**Never cut:** failed-repair block, successful-repair certificate, uncertain refusal, certificate tamper test, model contract validation, demo reset/fallback.

---

## 4. Risks and mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---:|---|
| Before/after data is challenged as reconstructed | High | High | Label it everywhere; use same-recording failed case; show held-out uncertain case; explain the logic is real |
| Model scope too narrow | High | Medium | Scope to bearing vibration; use “within validated scope”; do not claim general repair verification |
| Streamlit UI time sink | Medium | High | Build one screen; reuse existing CSS; API-first fallback |
| Certificate crypto bugs | Medium | High | Use a vetted library; test every field; keep canonicalization simple; fallback to server verification |
| Signing key leaked/committed | Low | High | Env/file outside repo; `.gitignore`; rotate demo key before submission |
| No Git baseline | High | Medium | Preserve copy immediately; init repo; tag baseline |
| Python/dependency drift | High | Medium | Python 3.11 venv; pinned requirements; document exact commands |
| Judge asks “why not CMMS feature?” | High | High | Emphasize refusal + physical evidence + portable certificate; show negative case |
| Demo network/hardware failure | Medium | High | Offline fallback; pre-recorded video; loopback path |
| Team integration conflict | Medium | Medium | Freeze API contract at hour 8; separate files; daily 10-min sync |

---

## 5. Post-hackathon continuation (only if the demo works)

1. **Customer discovery:** interview 10 service managers/facility leads; test whether callbacks are a controllable pain and whether they would add a capture step.
2. **Real repair data:** partner with a service company; capture before/after on actual bearing replacements; measure false-certification and refusal rates.
3. **Model expansion:** add sensor/asset types only after the closure workflow is validated; do not lead with model accuracy.
4. **CMMS integration:** one integration (e.g., UpKeep or Fiix) to make closure blocking native.
5. **Certificate trust:** publish the public key, verification spec, and retention policy; get a legal review before any “certification” language.
6. **Business model test:** per-technician SaaS + per-certificate fee; warranty/insurer pilot.

Do not claim product-market fit from hackathon interest.

---

## 6. Final checklist before submission

- [ ] Existing 33 tests still pass.
- [ ] New tests cover failed, success, uncertain, unavailable, tampered, invalid, offline.
- [ ] Demo seed/reset works twice in a row.
- [ ] API starts from a clean venv; dashboard loads.
- [ ] Certificate verifies offline with the public key.
- [ ] Every negative case produces no certificate.
- [ ] Reconstructed-data banner is visible in UI and README.
- [ ] Model version/hash and input contract visible.
- [ ] No private key, raw dataset, or PII committed.
- [ ] 90-second and 5-minute rehearsals completed.
- [ ] Fallback video and terminal commands ready.
- [ ] Known limitations documented.
- [ ] Final pitch avoids “revolutionary,” “first,” “AI-powered,” “calibrated,” and “legal certification.”
