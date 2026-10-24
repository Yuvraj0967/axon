# 04 — Competitive and Problem Validation

**Method:** current web sources fetched 2026-10-24, plus repository evidence.  
**Evidence labels:** **[Fact]** sourced; **[Hypothesis]** reasoned but unvalidated; **[Unknown]** requires customer research.  
No customer interviews, willingness-to-pay data, or private market data were fabricated.

---

## 1. FixProof — repair verification / closure assurance

### Problem evidence

- **[Fact]** Hydro, a pump repair/condition-monitoring company, published a July 1, 2026 case study asking the exact question: *"Did it actually solve the problem?"* It describes teams relying on a quick vibration check or waiting for failure, and presents before/after vibration data as the objective answer. The case study shows fin-fan vibration reductions of ~44% and ~71% at specific locations after maintenance.  
  Source: https://hydroinc.com/continuous-condition-monitoring/ (July 1, 2026)
- **[Fact]** Maintenance rework is a recognized reliability problem: work must be repeated when the original intervention did not restore the required condition; causes include wrong diagnosis, incomplete scope, incorrect part, workmanship, and missing verification. The source explicitly says a job should not be considered successful simply because the equipment starts.  
  Source: https://improvement.company/knowledge/maintenance-rework-analysis/ (August 14, 2026)
- **[Fact]** HVAC callback benchmarks (adjacent evidence, not industrial rotating equipment) put top-quartile callback rates at 1–2%, acceptable at 3–5%, concerning at 5–8%, with modeled total economic cost of $300–$600 per callback. The source explicitly says there is no peer-reviewed public dataset and definitions vary.  
  Source: https://www.builtontenth.com/hvac-research/hvac-callback-rate-benchmarks (May 3, 2026)
- **[Fact]** FleetRabbit markets "repair verification" for oilfield fleets with digital workflows, photo evidence, offline operation, and "immutable" records. It claims 40% fewer repeat repairs and 100% audit-ready documentation, but these are vendor marketing claims, not independently verified.  
  Source: https://fleetrabbit.com/industry/oil-and-gas/oilfield-repair-verification-process (April 22, 2026)
- **[Fact]** Warranty costs are material: U.S.-based manufacturers paid ~1.329% of product sales on warranty claims in 2024; appliance & HVAC claims were ~$1.279B. This supports the broader "prove the repair" economic context, not a direct FixProof TAM.  
  Source: https://www.warrantyweek.com/archive/ww20250403.html (April 3, 2025)

### What competitors do well

| Competitor | Strength | Gap FixProof can exploit |
|---|---|---|
| **Hydro Centaur** | Real before/after condition-monitoring case studies; deep pump domain; continuous data; service organization | Hardware/service-heavy; sold to large facilities; before/after is an analysis output, not a repair-closure gate or portable certificate; not aimed at small service contractors |
| **Augury** | Broad machine-health platform, portable Auguscope, AI agents, large customer base, 15+ years of data | Predictive/monitoring focus; does not position around blocking work-order closure or a signed repair certificate; enterprise sales |
| **Fluke / SKF / Emerson** | Best-in-class measurement hardware and vibration analysis; trusted brands | Tools and reports, not a workflow that binds evidence to a work order and refuses closure; analyst interpretation remains manual |
| **CMMS (ServiceTitan, UpKeep, Fiix, Maximo)** | Ubiquitous work-order system of record; scheduling, parts, invoicing; callback reporting | Records "completed" and photos/notes, not physical outcome; would need sensor/model integration to verify |
| **FleetRabbit** | Digital repair verification workflow, photo evidence, offline mobile, audit trail, compliance framing | Verifies documentation/photos/checklists, not the machine's vibration signature; no model-based pass/fail; claims are vendor marketing |
| **Vibration-analysis services** | Expert diagnosis, ISO-style reports, accountability | Expensive, periodic, slow; not at the point of repair closure; no software gate |

### Is the innovation already there?

- Before/after **condition monitoring** exists (Hydro).
- Digital **repair verification workflows** exist (FleetRabbit, CMMS checklists).
- **Sensor-based closure gate + signed certificate + offline edge evidence** is not visibly a product category in the sources reviewed. This is a gap, not proof of novelty. **[Hypothesis]** It is a viable wedge because the buyer (service/facility manager) needs a decision, not another dashboard.

### Buyer / user / decision-maker

- **User:** field technician (captures before/after; wants fast, clear pass/fail).
- **Buyer:** maintenance service manager or facility reliability lead (pays to reduce callbacks/rework; owns closure policy).
- **Economic beneficiary:** facility owner / warranty provider (avoids repeat downtime and invalid claims).
- **Decision-maker:** service manager for contractor deployments; facility manager/reliability lead for in-house teams.

### Measurable benefit

- Callback/rework rate (before vs after deployment).
- Repeat repair rate within 30/90 days.
- Work-order reopen rate.
- Mean time between repair and next fault.
- Warranty claim rejection/approval cycle time.
- Technician adoption / captures per work order.

These are measurable, but **no baseline data exists in the repo**. A pilot must establish them. **[Unknown]**

### Strongest argument against building it

> "This is a feature, not a product. Any CMMS can add a before/after vibration field; Hydro and Augury already do before/after monitoring; FleetRabbit already sells repair verification. A judge will ask why this needs to be a company."

**Rebuttal:** The wedge is not the dashboard or the checklist; it is the **conservative, model-based closure gate plus a portable, tamper-evident certificate that works offline**. CMMS vendors record assertions; Hydro/Augury sell monitoring; FleetRabbit verifies photos. None of the reviewed products combines physical evidence, uncertainty-aware refusal, and an offline-verifiable certificate at the work-order boundary. That is a real distinction — but it must be demonstrated, not asserted.

### What would invalidate it

- Service managers say their existing vibration tool/CMMS already blocks closure on evidence, and they would not pay separately.
- A CMMS or condition-monitoring vendor already ships this exact workflow at a comparable price.
- The binary model cannot distinguish failed vs successful repairs on comparable data.
- The demo requires reconstructed data that a domain judge considers misleading.

---

## 2. ProofLayer — verifiable decision records for physical AI

### Problem evidence

- **[Fact]** AI audit/provenance is an active category. Hashirai markets "the missing audit trail for production AI," with signed records, cross-provider traceability, and "defensible evidence exports."  
  Source: https://hashirai.com (accessed 2026-10-24)
- **[Fact]** AI audit trails are described as needing training-data provenance, model version, inference parameters, feature distributions, calibration, explanations, and the relationship between model output and final decision.  
  Source: https://aisecurityandsafety.org/en/glossary/ai-audit-trail/ (accessed 2026-10-24)
- **[Fact]** Hashirai's focus is LLM/agent/tool-call workflows across providers; its examples are prompts, completions, and agent actions, not physical sensor decisions at the edge. This leaves a possible physical-world gap.

### Competitors

- Hashirai (AI record infrastructure, signed records, audit exports)
- AI governance platforms (ertas.ai, Openlayer, Fiddler, Arize, WhyLabs)
- Model registries/MLflow, Sigstore/SLSA (artifact provenance)
- SIEM/logging stacks
- CMMS/condition-monitoring vendor audit logs

### Strongest argument against

> "This is 'Hashirai for machines' — an infrastructure category with entrenched AI-governance vendors, no clear buyer in a hackathon, and a demo that is a JSON verification screen. It is technically impressive but commercially vague."

**Rebuttal:** Physical decisions have different evidence: sensor input contracts, edge inference, model/feature thresholds, and human confirmation. Hashirai does not address that. But the burden is high: the demo must make an auditor's workflow visceral, not just show a signature.

### What would invalidate it

- Buyers say existing logs/model cards suffice.
- A physical-AI vendor already ships end-to-end signed decision records.
- The hackathon is not about trust/governance, so judges see it as plumbing.

---

## 3. AssetPass — verifiable condition passport for used equipment

### Problem evidence

- **[Fact]** eBay launched a "Verified Condition" program for heavy equipment with in-person inspections by bidadoo, multi-point condition reports, five-star ratings, and purchase protections up to $200,000.  
  Source: https://www.ebayinc.com/stories/news/ebay-brings-verified-condition-program-to-heavy-equipment-category/ (accessed 2026-10-24)
- **[Fact]** IronSpector markets inspection/valuation reports for used equipment, turning condition into market-backed valuation support.  
  Source: https://www.ironspector.com (accessed 2026-10-24)

### Competitors

- eBay Verified Condition/bidadoo, IronSpector, equipment dealers, third-party inspection firms (SGS, Bureau Veritas), marketplace condition reports, maintenance-record platforms.

### Strongest argument against

> "Verified condition reports already exist and are backed by human inspectors and marketplace guarantees. A single vibration test is a narrow, gameable signal; buyers will not trust a 'passport' that only checks bearings."

**Rebuttal:** The existing reports are visual/checklist-based; a sensor-backed, signed record adds evidence and portability. But the scope must be explicit ("bearing vibration within validated range"), which makes it a narrow feature unless expanded to multiple modalities. This is weaker than FixProof because the buyer's trust problem is broader than one sensor.

### What would invalidate it

- Buyers say a vibration-only passport is not worth more than an existing inspection.
- Marketplaces require their own inspection partners; no API access.
- Liability/insurance concerns dominate.

---

## 4. Sentinel — offline condition monitoring

### Competitors

- Augury, Fluke, SKF, Emerson, Petasense, Hydro Centaur, Senseye, maintenance Inc., and many regional PdM providers.
- CMMS vendors adding condition monitoring.
- Low-cost IoT vibration sensors.

### Strongest argument against

> "This is the current product with a different landing page. The model is binary, the data is lab data, and there is no hardware. Augury has 1.1B+ hours of machine readings and 170+ manufacturers; a hackathon team cannot out-execute that in a weekend."

**Verdict:** Reject as the primary pivot. It is the crowded category the repo is already in.

---

## 5. GateKeep — edge model deployment assurance

### Competitors

- MLflow/model registries, container signing (Sigstore/SLSA), CI/CD, NannyML/Arize/Fiddler (monitoring), vendor-specific edge deployment tools.

### Strongest argument against

> "This is a CI check, not a product. Model registries and containers already handle versioning; input contracts are a library concern. The buyer is a platform engineer who may build it in-house."

**Verdict:** Technically credible, but weaker user value and demo emotion than FixProof.

---

## 6. Market timing and category creation

### Why FixProof could exist now

- **[Fact]** Condition-monitoring hardware and edge inference are commoditizing; the differentiator shifts to workflow and trust.
- **[Fact]** Repair verification is already a named workflow in field service (FleetRabbit) and a named benefit in condition monitoring (Hydro). The category is forming, not hypothetical.
- **[Hypothesis]** Small/mid service organizations are underserved: enterprise platforms are expensive; CMMS records are assertions; vibration analysts are periodic.
- **[Hypothesis]** Warranty/insurance pressure increases willingness to pay for proof.

### Why it might not

- **[Unknown]** No direct customer interviews. We do not know whether service managers will pay, or whether they perceive callbacks as a controllable problem.
- **[Unknown]** Whether a binary bearing model is enough to change closure behavior; many repairs are not bearing-related.
- **[Unknown]** Whether technicians will accept another capture step under time pressure.
- **[Unknown]** Whether CMMS vendors will bundle this and erase the wedge.

---

## 7. Competitive conclusion

FixProof has the clearest **problem → workflow → evidence → demo** chain. Its competition is real but fragmented: monitoring vendors provide data, CMMS provides process, inspection platforms provide checklists. The unoccupied position is **"the physical proof layer at repair closure."**

ProofLayer is the strongest runner-up on technical depth and novelty if the hackathon theme is AI trust/governance. AssetPass is the runner-up on marketplace/circular-economy fit. Sentinel should not be the pivot; it is the current category.
