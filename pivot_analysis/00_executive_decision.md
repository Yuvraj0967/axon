# 00 — Executive Decision

**Repository audited:** `/home/pulkithanda/Downloads/axon-feature-edge(2)/axon-feature-edge`  \n**Decision date:** 2026-10-24  \n**Decision:** **Pivot to FixProof** — repair verification and closure assurance for rotating equipment. Do not refine the current bearing-diagnostics dashboard as the core product.

---

## The decision in one paragraph

The code today is a well-engineered **bearing-diagnosis demo**: a packaged Random Forest classifies 4,096-sample vibration windows, a Raspberry Pi-style edge path sends compact results over a tested LoRa-style protocol, and a Streamlit dashboard displays the evidence. It is not a defensible product in the crowded predictive-maintenance category. Its strongest asset is not the classifier; it is the **auditable decision pipeline** — strict input/model contracts, uncertainty/refusal states, durable offline delivery, and provenance-aware records. The best use of that asset is **FixProof**, a workflow that makes a repair prove itself with before/after vibration evidence, a conservative verdict, and a signed, offline-verifiable certificate. FixProof can **block a work order** when the machine’s signature says the repair failed, **certify** a real repair, and **refuse** when the evidence is uncertain or incomparable. That is a new product category, a memorable demo, and a feasible build with the existing code.

---

## 1. What is the product today, based on the code?

A **bearing vibration diagnostic demo**, not a production product:

- Input: exactly 4,096 samples at 64 kHz (validated; wrong inputs rejected).
- Model: packaged Random Forest, 2 classes (`healthy`, `other_bearing_damage`), 200 trees, model version `axon-bearing-rf-ef4473b3cee7`.
- Output: a typed diagnostic record with status, confidence, evidence, alternatives, missing information, model version, and a simulated flag.
- Edge: local inference → SQLite outbox → LoRa v2 binary frame with CRC → gateway spool/dedupe → FastAPI ingest.
- UI: Streamlit dashboard for live/replay diagnostics, waveform, features, uncertainty, and bearing schematic.
- Data: 8 real Paderborn windows (4 recordings × 2 windows), CC-BY-NC-4.0; K001/KA04 are training-partition examples, K003/KI04 are held-out.
- Tests: **33 passed** in a Python 3.11 venv with pinned dependencies. The system Python 3.14 environment fails due to missing `psycopg2` and scikit-learn version drift.
- Gaps: no Git repo, no auth/tenancy, no DB migrations, no hardware capture validation, no CI, empty repair-doc/cost catalogs, uncalibrated binary model.

**Evidence:** `01_codebase_audit.md`; `docs/` and code; live API/dashboard/loopback runs.

---

## 2. What is the biggest weakness in its current positioning?

**It is a commodity classifier wrapped in a nice demo, aimed at a crowded category.** “Bearing diagnostics” competes with Augury, Fluke, SKF, Emerson, Hydro, Petasense, and every CMMS with a vibration integration. The model is binary, lab-trained, uncalibrated, and cannot localize a race defect or predict remaining life. The dashboard displays a prediction but does not change the user’s next action. A judge can dismiss it as “another predictive-maintenance dashboard” without engaging the engineering.

The second weakness is **demo credibility**: K001/KA04 are training examples, so the live loopback produces confidence 1.0 and looks perfect. The held-out KI04 case is actually uncertain, which is more honest but less flashy.

**Evidence:** `04_competitive_validation.md`; `ml/artifacts/bearing/active/evaluation.json`; live loopback output.

---

## 3. What is the strongest technical asset in the repository?

**The end-to-end, auditable decision pipeline — not the model.**

Specifically:

1. A typed diagnostic record with uncertainty, alternatives, missing information, confirmation requirement, model version, and simulated flag (`shared/diagnosis.py`, `backend/main.py`).
2. A strict model/input contract that rejects wrong sample rate, window length, feature order, artifact hash, or library version (`ml/bearing/bundle.py`).
3. Durable offline delivery: SQLite outbox before send, gateway spool before ACK, event-id dedupe, retry, restart behavior (`edge/lora_transport.py`, `edge/lora_gateway.py`, `shared/lora_protocol.py`).
4. Provenance-aware replay with license, checksums, documented labels, and a clear separation between dataset label and model decision (`backend/paderborn_replay.py`).
5. A tested binary protocol with CRC, typed statuses, ACK, and gateway expansion.

These are **harder to reproduce** than the Random Forest. They enable a product that can **prove** a decision, not just make one.

**Evidence:** `02_hidden_assets.md`; tests in `tests/test_lora_protocol.py`, `tests/test_bearing_integration.py`, `tests/test_backend.py`.

---

## 4. What should the product become?

**FixProof — repair verification / maintenance closure assurance.**

- **Pitch:** *A repair isn’t done until the machine proves it.*
- **User:** field technician; **buyer:** maintenance service manager or facility reliability lead.
- **Input:** before/after vibration windows + asset/component/work-order/operating-condition metadata.
- **Transformation:** contract validation → model inference → comparability check → conservative verdict.
- **Output:** `VERIFIED` + signed certificate, `NOT VERIFIED` + reasons, or `INCONCLUSIVE` / `CANNOT_VERIFY` + refusal.
- **Core loop:** open work order → capture before → repair → capture after → verify → close only with a certificate.
- **Scope:** bearing vibration on rotating equipment, within the validated model contract. Not a full CMMS, not continuous monitoring, not remaining-life prediction.

**Evidence:** `06_winning_product_blueprint.md`.

---

## 5. Why is that pivot stronger than the current direction?

1. **New decision, not another dashboard.** It changes whether a work order closes; the current product only displays a diagnosis.
2. **New category, less crowded.** It sits between condition monitoring (data/alerts) and CMMS (process/paperwork). The reviewed competitors do one or the other; the closure gate + signed certificate is a gap.
3. **Uses the strongest assets.** The evidence record, uncertainty policy, model contract, and durable delivery become the product, instead of being implementation details behind a commodity classifier.
4. **Memorable demo.** “The repair was marked done; the machine says it wasn’t” is a clear villain/hero story, with a tangible certificate and tamper test.
5. **Feasible.** No new ML, no hardware required for the fallback; P0 is ~24–36 engineer-hours.
6. **Expansion path.** Repair closure → equipment handover → warranty claims → insurance evidence → CMMS integration.

The current direction would require out-modeling Augury or out-dashboarding a CMMS. The pivot requires executing a workflow and evidence chain that the repo already partly has.

---

## 6. Who specifically benefits?

- **Field technician:** a fast, clear pass/fail instead of guessing; proof that the repair was done correctly.
- **Maintenance service manager:** fewer callbacks/rework; a defensible closure policy; a portable record for the customer.
- **Facility reliability lead:** evidence that contractor work actually fixed the machine; fewer repeat outages.
- **Warranty administrator / insurer (expansion):** sensor-backed evidence for claims and disputes.
- **Small/mid service organizations:** an affordable alternative to enterprise condition-monitoring platforms and periodic analyst reports.

---

## 7. What is the single capability that will make the product memorable?

**The closure gate that can say “NOT VERIFIED” — and prove it.**

Not “AI diagnoses bearings.” Not “a dashboard.” The memorable moment is:

> A work order says the bearing was replaced. FixProof captures the after-repair signature, sees the same damage probability, and refuses to close the work order. Then a real replacement verifies healthy, and the certificate checks offline; one changed byte breaks it.

That is a decision with a physical consequence, backed by evidence. It is easy to explain, hard to fake, and visually clear.

---

## 8. What can be demonstrated with working code?

The baseline already demonstrates:

- Real Paderborn windows running through the packaged model.
- Correct healthy/damaged classifications and an honest uncertain case (KI04).
- Contract validation (wrong sample rate/window rejected).
- Local edge inference, binary LoRa frame, CRC, outbox, gateway dedupe, ACK, API ingest.
- Dashboard history and model status.
- 33 passing tests.

The pivot adds (and must demonstrate):

- Repair session create/capture/verify.
- `NOT_VERIFIED` on a failed repair; `VERIFIED` on a successful replacement; `INCONCLUSIVE` on KI04; `CANNOT_VERIFY` with no model.
- Signed certificate + offline verification + tamper rejection.
- Comparability refusal (asset/model/rate/window/condition).
- Negative tests proving no certificate on failed/uncertain/unavailable cases.

**Do not claim** the successful before/after is a real chronological repair. It is reconstructed from real recordings and must be labeled.

---

## 9. What are the biggest reasons the pivot could fail?

1. **“Feature, not product.”** A CMMS or monitoring vendor could bundle before/after verification; the judge may see the workflow as a feature.
2. **Data credibility.** The before/after pairs are reconstructed, not a recorded repair; a domain judge may reject the demo.
3. **Model scope.** A binary lab model cannot verify most repairs; the product must stay narrow and refuse often.
4. **Buyer/adoption.** Contractors may not want proof of failure; the buyer may need to be the facility/warranty side. No customer interviews exist.
5. **Certificate trust.** Ed25519 makes records tamper-evident, not legally certified; key management and device identity are P2.
6. **Rubric fit unknown.** If the hackathon is about AI governance, ProofLayer may score better; if it is circular economy, AssetPass may. If it is pure model accuracy, none of these wins.

**Mitigation:** label the data; scope the claims; lead with the refusal and the failed-repair case; have a hardware/real-data pilot plan; keep the demo under 5 minutes with a fallback.

---

## 10. What must be built first?

In order:

1. **Baseline preservation + reproducible env** (Python 3.11, pinned deps, 33 tests green, API/dashboard start).
2. **Repair session domain + API/store** (create, capture before/after, get/list).
3. **Verdict engine + comparability** (VERIFIED / NOT_VERIFIED / INCONCLUSIVE / CANNOT_VERIFY / NOT_APPLICABLE).
4. **Certificate** (canonical JSON, Ed25519 sign/verify, offline CLI, tamper tests).
5. **Dashboard repair workspace + seed scenarios** (failed, success, uncertain).
6. **Negative/offline tests + demo reset/fallback.**

The certificate is the long pole; do not start with QR codes or visual polish.

---

## 11. What must not be built?

- A full CMMS (scheduling, invoicing, inventory, dispatch).
- A continuous-monitoring/alerting platform.
- Remaining-useful-life prediction.
- A general LLM chatbot or repair-advice generator.
- A new ML model or synthetic training pipeline.
- A blockchain/token.
- A marketplace.
- A legal certification claim.
- Hardware acquisition unless already available and validated.
- Multi-tenant auth/RBAC for the hackathon (document the gap; do not pretend it is secure).

---

## 12. What evidence would prove the pivot is working?

**Hackathon evidence (must have):**

- Failed repair → `NOT_VERIFIED`, no certificate.
- Successful replacement → `VERIFIED`, valid certificate.
- Held-out uncertain case → `INCONCLUSIVE`, no certificate.
- Model unavailable → `CANNOT_VERIFY`, no certificate.
- Tampered certificate → invalid.
- Wrong input/comparability → no certificate.
- Existing + new tests pass; demo reset works twice.
- Certificate verifies offline with the public key.

**Post-hackathon evidence (would prove the business):**

- 10 service-manager interviews; at least 3 say callbacks/rework are a top-3 controllable cost.
- 20 real before/after repairs captured; false-certification rate measured; refusal rate acceptable.
- Callback/reopen rate reduction in a pilot.
- A CMMS integration pilot.
- Willingness to pay (per technician or per verified repair).

No customer validation exists yet; do not claim it.

---

## 13. Final recommendation

**Pivot. Do not refine the current bearing dashboard as the core product.**

Build **FixProof** as a thin, complete, evidence-backed repair-closure workflow on top of the existing diagnostic pipeline. Keep the bearing model as the first validated component. Make the **refusal** and the **signed certificate** the center of the demo. Do not add breadth; add proof.

If the hackathon theme is explicitly **AI governance/trust**, the runner-up **ProofLayer** may score higher; if it is **circular economy/used equipment** and a marketplace partner is available, **AssetPass** may. Absent those, FixProof is the strongest intersection of problem, novelty, demo impact, and feasibility.

---

## 14. Prioritized next-step checklist (after authorization)

### First 2 hours
- [ ] Preserve a baseline copy; initialize Git (or a tagged baseline) if approved.
- [ ] Create Python 3.11 venv; install pinned requirements + `cryptography` + `qrcode[pil]`.
- [ ] Run `AXON_STORAGE_MODE=memory python -m pytest -q`; save 33-pass baseline.
- [ ] Start API + dashboard; verify `/ready`, model status, Paderborn catalog, loopback.
- [ ] Write `demo/repairs/README.md` with provenance/disclosure.

### First 8 hours
- [ ] Freeze API/certificate contracts.
- [ ] Implement repair session model/store/routes.
- [ ] Implement capture before/after via replay windows and event IDs.
- [ ] Add API tests.

### First 14 hours
- [ ] Implement verdict matrix + comparability + reasons.
- [ ] Implement certificate canonicalization + Ed25519 sign/verify + CLI.
- [ ] Add tamper/negative tests.
- [ ] Verify no certificate on failed/uncertain/unavailable/invalid cases.

### First 26 hours
- [ ] Build one repair workspace screen.
- [ ] Seed `WO-1042` failed, `WO-1043` success, `WO-1044` inconclusive.
- [ ] Add certificate panel + verification result.
- [ ] Run end-to-end with packaged windows.

### Final 10 hours
- [ ] Add offline/idempotency scenario or document baseline evidence.
- [ ] Record fallback video.
- [ ] Rehearse 90s and 5min scripts.
- [ ] Freeze features; clean run; final checklist.
- [ ] Do not add new model classes, hardware, or CMMS features.

---

## 15. The one-sentence decision

**Build FixProof: make the machine sign off on the repair, and make that sign-off verifiable.**
