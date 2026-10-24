# 05 — Scoring and Decision

**Scale:** 100 points, default weights from the brief.  
**Important:** the actual hackathon rubric, theme, duration, team size, and hardware access are unknown. Scores for "fit with rubric" are therefore provisional. All other scores are evidence-based from the audit and competitive review.

Weights: Problem 15 · Novelty 15 · Technical depth 15 · Demo 15 · Feasibility 15 · Rubric fit 10 · Evidence 5 · Sustainability 10.

---

## 1. Score table

| Candidate | Problem | Novelty | Tech | Demo | Feasibility | Rubric | Evidence | Sustainability | **Total** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **FixProof** | 14 | 12 | 13 | 14 | 14 | 8 | 4 | 8 | **87** |
| **ProofLayer** | 12 | 10 | 14 | 12 | 11 | 8 | 3 | 7 | **77** |
| **AssetPass** | 12 | 9 | 10 | 12 | 14 | 8 | 3 | 6 | **74** |
| WarrantyWitness | 12 | 9 | 11 | 11 | 12 | 7 | 3 | 7 | **72** |
| GateKeep | 9 | 9 | 12 | 10 | 13 | 7 | 2 | 6 | **68** |
| Sentinel | 13 | 4 | 9 | 9 | 13 | 8 | 4 | 6 | **66** |
| Relay | 8 | 10 | 13 | 10 | 12 | 6 | 2 | 5 | **66** |
| CommonGround | 7 | 8 | 11 | 7 | 12 | 6 | 2 | 4 | **57** |
| Echo | 13 | 7 | 4 | 11 | 5 | 7 | 1 | 5 | **53** |
| Loop | 9 | 8 | 8 | 8 | 8 | 6 | 1 | 5 | **53** |

Scores are not precise measurements. They are a decision aid; a ±5 swing is plausible for any candidate if the rubric/theme differs.

---

## 2. Justification by criterion

### FixProof — 87

- **Problem 14/15.** Repair rework/callbacks are frequent, costly, and explicitly recognized by condition-monitoring and maintenance-quality sources. Adjacent HVAC benchmark: 3–5% acceptable, 5–8% concerning, $300–$600 modeled cost per callback. Industrial evidence is qualitative (Hydro case study), not a quantified TAM. No customer interviews. **[Uncertain]**
- **Novelty 12/15.** Before/after monitoring exists (Hydro); digital repair verification exists (FleetRabbit); but the combination of sensor-based verdict, uncertainty-aware refusal, closure gate, and signed portable certificate is not visibly a product. Moderate novelty, not "first of its kind."
- **Tech 13/15.** Reuses the hardest existing pieces (edge inference, contract validation, outbox/spool, protocol, diagnostic schema). New work is verdict logic, comparability, signing, and UI. Technically credible without a new model.
- **Demo 14/15.** Strong villain/hero narrative; can show failed repair blocked, successful repair certified, uncertain case refused, tampered certificate rejected, offline event surviving. Caveat: the successful before/after pair is reconstructed from Paderborn recordings, not a recorded repair. Must be labeled.
- **Feasibility 14/15.** P0 is achievable in ~24–36 engineer-hours with one strong engineer or two average ones. No hardware required for the fallback. Critical path is verdict + certificate + dashboard.
- **Rubric 8/10.** Likely strong for industrial AI, applied AI, impact, and "real-world problem" rubrics. Weaker if the rubric is purely technical novelty or consumer/social impact. Unknown.
- **Evidence 4/5.** Problem evidence from current industry sources; no primary customer evidence. Strong repo evidence for technical claims.
- **Sustainability 8/10.** Clear buyer, recurring workflow, expansion to handover/warranty, potential CMMS partnership. Adoption and liability risks are real.

### ProofLayer — 77

- **Problem 12.** AI auditability is important and current, but the buyer is vague for a hackathon; physical-AI provenance is a subset of a crowded governance category.
- **Novelty 10.** Hashirai and AI-governance vendors already occupy "verifiable AI record." The physical edge angle is distinct but not enough to claim a new category.
- **Tech 14.** Highest technical depth: canonicalization, signatures, hash chain, offline verifier, lineage. But more implementation risk in the time available.
- **Demo 12.** Tamper detection is crisp, but a JSON verification screen is less emotionally compelling than a repair closure.
- **Feasibility 11.** More from-scratch work; key management and canonicalization need care.
- **Rubric 8.** Strong if the theme is trust/governance/security; weak if the theme is industrial operations.
- **Evidence 3.** Good category evidence, no direct buyer validation.
- **Sustainability 7.** Plausible infrastructure business, but crowded and long sales cycles.

### AssetPass — 74

- **Problem 12.** Used-equipment trust is real and marketplaces are investing in it (eBay Verified Condition, IronSpector). But a vibration-only passport is narrow.
- **Novelty 9.** Condition reports exist; sensor-backed signed evidence is a differentiator, not a new category.
- **Tech 10.** Mostly signing/reporting; model scope is narrow; less use of the durable edge pipeline.
- **Demo 12.** QR/passport verification is tangible; less dramatic than preventing a bad repair.
- **Feasibility 14.** Simple to build from the existing stack.
- **Rubric 8.** Strong for circular economy/marketplace themes; weaker for industrial AI.
- **Evidence 3.** Marketplace evidence exists; no buyer interviews.
- **Sustainability 6.** Marketplace partnerships and liability are hard; one modality limits trust.

### Why Sentinel is not the answer (66)

It is the current product. Problem significance is high, but novelty is 4/15: Augury, Fluke, SKF, Emerson, Petasense, Hydro, and CMMS vendors all occupy the space. The repo's model is binary and lab-trained, and there is no hardware. A hackathon judge can dismiss it as "another PdM dashboard" without engaging the engineering.

### Why Echo is rejected (53)

The current model requires 4,096 samples at 64 kHz. Phone audio is typically 44.1/48 kHz, different transfer function, different mounting, different fault physics. A credible product would need a new dataset and model. Demonstrating it in a weekend would require staged/fake outputs, violating the "no fake AI" rule.

### Why Loop is rejected (53)

The technician feedback endpoint exists but is write-only. There is no calibration/retraining data in the repo. A demo would either be trivial ("we stored a confirmation") or fake ("the model improved"). Reject for this event; revisit post-hackathon with real feedback data.

---

## 3. Top three trade-offs

### FixProof vs ProofLayer

| Dimension | FixProof | ProofLayer |
|---|---|---|
| User | Service/facility manager | Industrial AI/audit team |
| Outcome | Repair closure / callback reduction | Defensible AI decision record |
| Demo emotion | High ("the repair wasn't done") | Medium ("the record verifies") |
| Technical novelty | Moderate | High |
| Buyer clarity | Moderate-high | Low-moderate |
| Build risk | Lower | Higher |
| Category crowding | Fragmented | Crowded AI governance |

**FixProof wins** because a hackathon rewards a concrete, understandable outcome. ProofLayer is the better choice only if the rubric explicitly weights AI governance/security and the judges are technical auditors.

### FixProof vs AssetPass

| Dimension | FixProof | AssetPass |
|---|---|---|
| Frequency | Every repair | Occasional sale/handover |
| Buyer control | Service/facility manager controls closure | Marketplace/buyer/seller multi-party |
| Data need | Before/after pair | One inspection + identity |
| Demo | Failed vs successful repair | QR passport |
| Expansion | Handover, warranty, resale | Repair, warranty |
| Adoption risk | Moderate | High (marketplace partnerships) |

**FixProof wins** because repair closure is frequent and the buyer can adopt without a marketplace. AssetPass is a feature/expansion of the same evidence layer, not the wedge.

### FixProof vs WarrantyWitness

WarrantyWitness has a clear economic buyer but requires claims data, policy rules, and legal/compliance work. It is a vertical application of the same evidence; FixProof is the upstream workflow that generates the evidence. Build FixProof first; warranty is an expansion.

---

## 4. Primary recommendation

**Pivot to FixProof: repair verification and closure assurance for rotating equipment.**

It beats the alternatives because:

1. It converts the repo's strongest hidden asset — auditable, uncertainty-aware evidence — into a user decision, not another dashboard.
2. It avoids the crowded "predictive maintenance" category while staying causally connected to the model and edge pipeline.
3. It has a memorable, demonstrable claim: **the system can refuse to close a work order because the machine's vibration signature says the repair failed.**
4. It is feasible without new ML or hardware; the P0 can be built and tested in the hackathon.
5. It has a credible expansion path: handover, warranty, insurance, and CMMS integration.

**What must be true for this to win:**

- The demo must show a **failed repair blocked**, a **successful repair certified**, an **uncertain case refused**, and a **tampered certificate rejected**.
- The reconstructed-data caveat must be explicit and professional, not hidden.
- The certificate must verify offline with a public key and fail on any modification.
- The UI must make the verdict and evidence understandable in under 10 seconds.
- The pitch must not claim the model is calibrated, general-purpose, or a legal certification.

**What would make ProofLayer preferable:** the hackathon theme is explicitly AI trust/governance/security, the rubric weights cryptographic provenance and technical novelty over user workflow, and the team has a strong crypto/backend engineer.

**What would make AssetPass preferable:** the theme is circular economy/used equipment/marketplace trust, and the team has a marketplace or inspection partner who can supply real listings and distribution.

**If none of these conditions hold:** do not pivot to a new domain; improve the current demo's honesty and execution, but expect a weaker competitive position. There is no guaranteed win.

---

## 5. Confidence and unknowns

| Claim | Confidence | Basis |
|---|---|---|
| Current product is crowded | High | Named incumbents; category breadth |
| Hidden asset is evidence/delivery, not model | High | Code audit; tests; uniqueness assessment |
| Repair verification is a real problem | Medium-high | Industry sources; no primary interviews |
| FixProof can be built in time | High | Reuse analysis; P0 scope |
| FixProof demo is compelling | Medium-high | Narrative; data reconstruction caveat |
| Buyers will pay | Low-medium | No willingness-to-pay evidence |
| Hackathon rubric fit | Unknown | Rubric/theme not provided |
| Model can verify repairs reliably | Medium-low | Binary lab model; limited scope |

The decision is robust to the technical unknowns but sensitive to the hackathon theme and the team's ability to execute the demo.
