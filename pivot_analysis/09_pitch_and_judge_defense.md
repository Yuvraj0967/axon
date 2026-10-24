# 09 — Pitch and Judge Defense

**Rule:** every claim must be traceable to working code or a labeled source. Do not optimize for how impressive the idea sounds; optimize for what the judge can verify.

---

## 1. 30-second pitch

> “Every maintenance team has a graveyard of machines marked ‘fixed’ that came back. FixProof makes a repair prove itself. It captures vibration before and after the repair, applies a conservative model verdict, and issues a signed certificate — or refuses to close the work order. In our demo, a bearing marked ‘replaced’ still shows 100% damage; FixProof blocks closure. A real replacement verifies healthy; the certificate checks offline; change one byte and it fails. A repair isn’t done until the machine proves it.”

---

## 2. Two-minute pitch

### 0:00–0:25 — Problem

“A work order is usually closed when a technician says the repair is done. There’s no comparable evidence that the machine’s condition changed. Failed repairs come back as callbacks, repeat downtime, and warranty disputes.”

### 0:25–0:50 — Existing alternatives

“CMMS records completion and photos. Vibration tools produce data, but an analyst interprets it later. Continuous-monitoring platforms like Hydro or Augury provide data and alerts, but they don’t block a work-order closure. So the decision is still a human assertion.”

### 0:50–1:15 — Insight

“The missing product isn’t another prediction dashboard. It’s a **closure gate**: before/after evidence, a conservative verdict, and a portable proof. The system must be able to say ‘not verified’ — and prove why.”

### 1:15–1:45 — Product + demo

“FixProof captures a before window and an after window, checks they’re comparable, runs the existing bearing model, and returns `VERIFIED`, `NOT VERIFIED`, or `INCONCLUSIVE`. Only a verified repair gets a signed certificate bound to the model version and both evidence hashes. In the demo, the failed repair is blocked; the successful replacement is certified; the uncertain held-out case is refused; a tampered certificate is rejected.”

### 1:45–2:00 — Why us / next

“We’re reusing a working edge inference and evidence pipeline, not a mock. The first scope is bearing vibration on rotating equipment. Next: real repair data with a service partner and a CMMS integration. A repair isn’t done until the machine proves it.”

---

## 3. Five-minute presentation outline

| Time | Section | Content |
|---:|---|---|
| 0:00–0:40 | Hook | Work order marked “fixed”; callback; the cost of unverified repair |
| 0:40–1:20 | Problem | No objective closure; CMMS records assertions; monitoring doesn’t gate closure |
| 1:20–1:50 | Insight | Verification, not prediction; before/after + refusal + certificate |
| 1:50–2:20 | Product | Three verdicts; signed certificate; offline edge evidence |
| 2:20–4:20 | Live demo | Failed repair blocked; success certified; tamper rejected; uncertainty refused |
| 4:20–4:40 | Technical distinction | Server-recomputed verdict, model contract, outbox/spool, signature/verification |
| 4:40–5:00 | Business + close | Buyer, pilot, expansion; “the machine signs off” |

### Slide list (7 slides max)

1. Title + one-line pitch.
2. The closed work order that wasn’t fixed (problem).
3. Why CMMS/monitoring/analyst reports don’t solve closure.
4. FixProof loop: before → repair → after → verdict → certificate.
5. Demo screenshots: NOT VERIFIED vs VERIFIED + certificate.
6. Technical proof: model contract, comparability, signature, tests.
7. Buyer/pilot/next step + close.

Do not put a wall of architecture on the main slides; keep the Mermaid diagram for the appendix/handout.

---

## 4. Timed live-demo script (5 minutes)

**Pre-demo:** API, dashboard, seed data, browser tabs, terminal with tests, certificate verifier, fallback video. Do not debug on stage.

| Time | Action | Say |
|---:|---|---|
| 0:00 | Show WO-1042 | “This work order says the bearing was replaced and is ready to close.” |
| 0:20 | Capture before (KA04 w0) | “Before: damage probability 1.0, status fault suspected.” |
| 0:45 | Mark repair done; capture after (KA04 w1) | “After the claimed repair: still 1.0.” |
| 1:10 | Verify | “FixProof refuses to close it. No certificate. The machine’s signature didn’t change.” |
| 1:40 | Open WO-1043; before/after (KA04 → K003) | “Now a real replacement scenario: before 1.0, after healthy 1.0.” |
| 2:20 | Verify | “Verified. Certificate bound to the model version, input contract, and both evidence hashes.” |
| 2:50 | Scan QR / open verifier | “Valid. The judge or auditor can verify it offline.” |
| 3:20 | Tamper certificate | “Change the verdict — invalid. The certificate is evidence, not a PDF.” |
| 3:50 | Open WO-1044 (KA04 → KI04 w0) | “Held-out damaged case: the model is uncertain, top probability 0.665. FixProof says inconclusive — no certificate.” |
| 4:20 | Optional model unavailable / offline | “No model or no network: cannot verify. It never turns uncertainty into a pass.” |
| 4:40 | Close | “A repair isn’t done until the machine proves it.” |

**Disclosure line (say it, don’t hide it):** “The before/after pairs are reconstructed from real Paderborn recordings on the same test rig and operating condition; this is not a recording of an actual repair. The model and verdict logic are real.”

---

## 5. Ten difficult judge questions

### Q1. Isn’t this just a feature a CMMS could add?

**Answer:** “A CMMS records that a human said the job is complete. It doesn’t have the model contract, the before/after inference, the comparability check, or the refusal policy. A CMMS can integrate us — that’s a distribution channel, not a reason the workflow doesn’t need to exist. The hard part is the evidence gate, not the work-order form.”

**Evidence:** show `NOT_VERIFIED` on a work order; show the verdict reasons; show the certificate.

### Q2. Hydro and Augury already do before/after condition monitoring. Why you?

**Answer:** “They sell monitoring and analysis; the output is a report or alert. We sell a closure decision: a work order cannot be certified until a comparable after-signature resolves the before-signature. Hydro’s own July 2026 case study shows before/after data is valuable; it also shows the workflow is still an expert service. We make it a portable, signed gate that a service manager can use without a vibration analyst on site.”

**Evidence:** Hydro case study; our failed-repair block; certificate.

### Q3. Your model is binary and lab-trained. How can it verify repairs?

**Answer:** “It can’t verify every repair. It verifies bearing vibration within its validated scope: healthy vs documented generic bearing damage, 4,096 samples at 64 kHz. The certificate states that scope. The product is the closure workflow; the model is replaceable as we add modalities. We do not claim race-level localization or remaining life.”

**Evidence:** model metadata/evaluation; `DIAGNOSIS_UNCERTAIN` on KI04; certificate scope field.

### Q4. Your demo data isn’t a real before/after repair. Isn’t that fake?

**Answer:** “The signals are real Paderborn recordings, the model is real, and the verdict code is real. The repair sequence is reconstructed and labeled on screen. The failed-repair case uses two windows of the same damaged recording, so the unchanged signature is genuine. The successful case uses a held-out healthy recording from the same test rig/condition. We are not claiming we physically repaired a bearing in the demo. The technical claim is the gate and the certificate, and those are executable.”

**Evidence:** manifest, checksums, disclosure banner, held-out KI04 uncertainty.

### Q5. Who pays, and what is the ROI?

**Answer:** “Initial buyer: maintenance service manager or facility reliability lead. The value is fewer callbacks/rework and faster closure. We would price per technician or per verified repair, with a warranty/insurer pilot later. We do not have willingness-to-pay data yet; the hackathon proves the workflow, not the market. The measurable pilot metrics are callback rate, reopen rate, and repeat repair rate.”

**Evidence:** adjacent callback benchmarks; do not invent a TAM.

### Q6. What stops a technician from gaming it?

**Answer:** “For the hackathon: server-side recomputation, comparable operating conditions, evidence hashes, and signed certificates. A technician can still capture a different machine or a different condition; we detect the metadata mismatch and refuse. We do not claim hardware tamper-proofing yet. Post-hackathon: device identity/attestation and supervised capture.”

**Evidence:** comparability failures; certificate signature.

### Q7. Why signatures? Why not a database record?

**Answer:** “A database record is only as trustworthy as the database and the person reading it. The certificate lets a third party verify the evidence offline, without trusting our server. It is tamper-evident, not blockchain, and not a legal certification. Ed25519 is fast and standard.”

**Evidence:** offline verifier; field-by-field tamper test.

### Q8. What happens when the model is wrong or uncertain?

**Answer:** “It refuses. `DIAGNOSIS_UNCERTAIN`, `MODEL_UNAVAILABLE`, or `SENSOR_DATA_INVALID` never produce `VERIFIED`. That’s the product: a false ‘pass’ is worse than a refusal. The held-out KI04 case is our live example: top-1 healthy at 0.665, below the 0.70 threshold, so it returns inconclusive.”

**Evidence:** KI04 live; negative tests.

### Q9. Why hasn’t this been built already?

**Answer:** “The pieces are recent: cheap edge inference, commodity vibration capture, and buyer pressure for evidence. Monitoring vendors optimize for coverage and alerts; CMMS vendors optimize for process. The closure gate sits between them. It’s a category-forming product, not a completely new science.”

**Evidence:** market sources; do not claim “first.”

### Q10. What would you do with the next 30 days?

**Answer:** “Get 10 service managers to test the workflow; capture real before/after data on 20 bearing replacements; measure false-certification and refusal rates; integrate one CMMS; then decide whether the wedge is repair closure or warranty evidence. We would not add more model classes before the closure workflow is validated.”

**Evidence:** pilot plan; no fake traction.

---

## 6. Three strongest objections (and honest answers)

### Objection 1 — “This is a feature, not a product.”

**Why a judge will say it:** CMMS + vibration tool + PDF seems assemblable.

**Answer:** “The product is the refusal policy and the evidence-bound certificate, not the form. A CMMS can record a pass; it cannot compute a comparable model verdict or let a third party verify the evidence offline. If a CMMS bundles it, that validates the workflow — and we can be the evidence layer inside it.”

**If the judge still disagrees:** concede the wedge is narrow and show the expansion to warranty/handover; do not pretend it is a platform on day one.

### Objection 2 — “The data is reconstructed.”

**Why a judge will say it:** the before/after pairs are not a chronological repair.

**Answer:** “Correct, and it’s labeled. The failed-repair case is the same damaged recording before and after: a real unchanged signature. The successful case uses a real held-out healthy recording from the same rig/condition. We are demonstrating the gate, not claiming a field repair study. The next step is a service-partner pilot with real repairs.”

**If the judge demands real repair data:** show the hardware capture contract and the pilot plan; do not fabricate.

### Objection 3 — “The model is too weak / too narrow.”

**Why a judge will say it:** binary classes, lab data, uncalibrated probabilities, 90.6% damage recall.

**Answer:** “Agreed. The model is a screening component with a stated scope, not a general repair oracle. The product can refuse, and the certificate states the scope. The architecture is model-agnostic; bearing vibration is the first validated modality. We are not claiming deployment readiness.”

**If the judge wants a better model:** explain that a better model does not solve the closure/evidence problem; it only changes the component. The product thesis is independent of model accuracy, as long as the system can say “inconclusive.”

---

## 7. Claims that must not be made

Do **not** say:

- “Revolutionary,” “first of its kind,” “world’s first,” “AI-powered” as a standalone virtue.
- “Calibrated confidence” or “100% accurate.” The probabilities are uncalibrated; a 1.000 output is a model probability on a demo window, not truth.
- “Predicts remaining useful life.” Not implemented.
- “Detects all bearing faults” or “localizes inner/outer race damage.” The model is binary healthy/generic damage.
- “Legal certification,” “compliance-certified,” “insurance-approved,” or “audit-proof.” The certificate is tamper-evident evidence, not a legal certification.
- “Real repair data” for the reconstructed demo scenarios.
- “Works on any machine, any sensor, or a phone.” The contract is 4,096 samples at 64 kHz.
- “Production-ready,” “secure,” “multi-tenant,” or “enterprise-grade.” No auth/tenancy/security review.
- “Prevents all callbacks.” It gates closure; adoption and capture quality determine outcomes.
- “Blockchain.” We use Ed25519 signatures, not a blockchain.
- “We have customer validation.” We have problem evidence and a demo, not customer interviews.

---

## 8. Judge handout (one page)

Include:

1. One-line pitch + QR to demo.
2. Before/after probability table for failed/success/uncertain.
3. Architecture in five boxes: capture → contract → model → verdict → certificate.
4. The three verdicts and the refusal policy.
5. Certificate verification command.
6. Evidence: test count, model hash, dataset license, disclosure.
7. Buyer/pilot/next step.
8. Limitations in one honest line.

The handout should be readable in 30 seconds and should not overclaim.

---

## 9. Closing line

> “Monitoring tells you a machine might fail. FixProof tells you whether the repair actually worked — and gives you a certificate the next person can verify. A repair isn’t done until the machine proves it.”
