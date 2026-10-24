# 03 — Radical Pivot Candidates

**Rule:** these differ in user, problem, workflow, value proposition, or product category — not just names. All are causally connected to capabilities verified in the audit. Scores are in `05_scoring_and_decision.md`.

---

## Candidate 1 — **FixProof** (recommended)

**Pitch:** *A repair isn't done until the machine proves it.* FixProof captures before/after vibration evidence, applies a conservative model verdict, and issues a signed, offline-verifiable repair certificate — or refuses to close the work order.

**Exact user:** Maintenance service manager or facility reliability lead at a small-to-mid industrial site (pumps, motors, compressors, HVAC) who closes 50–500 rotating-equipment work orders per year. End user: field technician. Economic buyer: service manager / facility manager / warranty provider.

**Painful, frequent, costly problem:** Work orders are closed on technician assertion or a quick "sounds better" check. Failed repairs return as callbacks, repeat downtime, warranty disputes, and lost trust. Industry-adjacent benchmarks put HVAC callbacks at 3–5% acceptable, 5–8% concerning, with modeled costs of $300–$600 per callback (Built on Tenth, May 2026; vendor/industry estimates, no peer-reviewed dataset). Hydro's July 2026 case study makes the same point for rotating equipment: teams often cannot answer "did the repair actually solve the problem?" without before/after data.

**Existing workaround:** Visual inspection, operator judgment, periodic vibration-analyst reports, waiting for the machine to fail again, or continuous-monitoring platforms that provide data but not a closure gate. CMMS records "completed"; it does not verify the physical outcome.

**Why now:** Cheap edge inference makes a local verdict possible; maintenance labor is scarce; warranty/insurance scrutiny is rising; condition-monitoring hardware is commoditizing. The differentiator is no longer "we have a model" — it is "we can prove the intervention worked."

**Primary input → transformation → output:** Two vibration windows (before/after) + asset/component/work-order/operating-condition metadata → contract validation, model inference, comparability check, conservative verdict → `VERIFIED` / `NOT VERIFIED` / `INCONCLUSIVE` + signed certificate or refusal.

**Existing capabilities used:** `ml/bearing/bundle.py`, `ml/bearing/signal.py`, `shared/diagnosis.py`, `backend/main.py`, `backend/paderborn_replay.py`, `edge/bearing_runner.py`, `edge/lora_transport.py`, `edge/lora_gateway.py`, `shared/lora_protocol.py`, `dashboard/app.py`.

**Built from scratch:** Repair-session domain model/API/store; before/after verdict engine; comparability gate; certificate canonicalization + Ed25519 signature + verifier; repair workspace UI; demo repair scenarios; tests.

**Differentiation:** Verification, not prediction. The system can **refuse to certify** and block closure. The certificate is portable and tamper-evident. It works with intermittent connectivity and any compatible capture source. It is a workflow product, not another monitoring dashboard.

**Competitors/alternatives:** Augury (machine health/predictive, not closure), Hydro Centaur (continuous monitoring with before/after case studies, hardware/service), Fluke/SKF/Emerson (measurement/analysis), CMMS (ServiceTitan/UpKeep/Fiix/Maximo — process records, not physical proof), FleetRabbit (digital repair verification with photos/checklists, not sensor/model evidence), vibration-analyst services (expensive, periodic).

**Smallest demonstrable version:** One work order, two captures. Failed repair: before=damaged, after=same damaged signature → `NOT VERIFIED`, closure blocked. Successful repair: before=damaged, after=healthy → `VERIFIED`, signed certificate. Tamper a certificate → verification fails. No hardware required; use packaged Paderborn recordings with explicit "reconstructed scenario" labels.

**60–90s demo:** "This work order says the bearing was replaced. The technician wants to close it. FixProof asks the machine. Before: 100% damage. After: still 100% damage. It refuses to close the work order. Now a real replacement: after is healthy within scope; it issues a certificate. Scan the QR: the record verifies offline. Change one byte: rejected. A repair is not done until the machine proves it."

**Hackathon scope:** P0 can be built in ~24–36 engineer-hours: repair API + verdict engine + certificate + one dashboard screen + 5 tests + seeded demo. Hardware optional.

**Biggest risks:** (1) Judges see it as a feature a CMMS could add. (2) Before/after demo data is reconstructed, not a real repair. (3) The binary model cannot verify all repair types. (4) Contractors may not want proof of failure; buyer may need to be the facility/warranty side. (5) Certificate is tamper-evident, not legally certified.

**Evidence that would invalidate:** Service managers say they already verify repairs with a vibration tool and would not pay for a separate closure product; CMMS vendors already block closure on sensor evidence; the model cannot distinguish a failed repair from a successful one on comparable data; the demo requires misleading data to be compelling.

---

## Candidate 2 — **AssetPass**

**Pitch:** A verifiable, sensor-backed condition passport for used industrial equipment — so a buyer can trust what the seller claims.

**Exact user:** Buyer/seller of used pumps, motors, compressors, or machine tools; equipment dealer; auction marketplace; lender taking equipment as collateral.

**Problem:** Used-equipment condition is self-reported or based on a visual inspection. Buyers discount heavily or demand teardowns; sellers with good machines cannot prove it; disputes are expensive. Existing condition reports are checklists/photos, not physical evidence.

**Workaround:** Third-party inspection (eBay Verified Condition/bidadoo, IronSpector, SGS/Bureau Veritas), maintenance records, visual inspection, price discount for uncertainty.

**Why now:** Online used-equipment commerce is growing; marketplaces are adding verified-condition programs; buyers want portable digital proof.

**Input → transformation → output:** A standardized vibration test + asset identity + inspection metadata → model verdict + evidence record → signed condition passport with scope/limitations and QR verification.

**Existing capabilities:** Same evidence/model/provenance stack as FixProof, plus manifest/license handling and dashboard.

**Built from scratch:** Asset identity/enrollment, inspection protocol, passport schema/signing, marketplace-facing verification page, chain-of-custody.

**Differentiation:** Physical evidence, not photo/checklist; portable, tamper-evident; explicit scope ("bearing vibration within validated range"), not a vague grade.

**Competitors:** eBay Verified Condition (in-person inspection + report), IronSpector (inspection/valuation), bidadoo, equipment dealers, third-party inspectors.

**Smallest demo:** Seller submits a used motor; AssetPass runs a vibration test; passport says "bearing condition: healthy within validated scope" or "damage suspected"; buyer scans QR and verifies; a tampered passport fails.

**60–90s demo:** "This motor is listed as 'runs great.' The buyer has no way to check. AssetPass generates a signed condition passport from a real vibration test. Scan it: the evidence, model version, and scope are visible. Change the verdict: verification fails."

**Hackathon scope:** Feasible, but the marketplace/buyer trust story needs a partner to be credible; one modality is narrow.

**Risks:** Condition reports already exist; one vibration test cannot certify a whole machine; marketplace adoption is hard; legal/liability claims; data license.

**Invalidation:** Buyers say a vibration-only passport is not worth more than an existing inspection report; marketplaces already require sensor evidence; the model's scope is too narrow to support a general "passport."

---

## Candidate 3 — **ProofLayer**

**Pitch:** A verifiable decision record for physical AI — every automated machine decision gets a reproducible evidence packet an auditor can check offline.

**Exact user:** Industrial AI platform team, regulated operator, insurer, or auditor who must defend an automated maintenance/safety decision.

**Problem:** AI decisions are logged as text; the chain from sensor input → model version → features → threshold → human action is fragmented. When an incident or audit happens, teams cannot reconstruct why the model said what it said. Existing AI governance tools focus on LLM/agent calls, not physical sensor decisions at the edge.

**Workaround:** Ad-hoc logs, model cards, spreadsheets, vendor reports, trust in the vendor.

**Why now:** EU AI Act/audit pressure, insurance scrutiny, edge AI proliferation, and the fact that physical decisions have safety/cost consequences.

**Input → transformation → output:** Diagnostic event + raw/derived evidence hash + model/feature/threshold metadata + human confirmation → canonical evidence packet + signature/hash chain → offline verifier verdict.

**Existing capabilities:** Diagnostic record schema, bundle hash/contract, durable event identity, provenance manifest, uncertainty statuses.

**Built from scratch:** Canonicalization, signing/key management, hash chain, verifier CLI/page, evidence retention, policy mapping, integrations.

**Differentiation:** Physical-world, edge-first evidence (not LLM prompts); includes uncertainty/refusal and model contract; works offline.

**Competitors:** Hashirai (AI decision record/audit), AI governance platforms (ertas, Openlayer), model registries/MLflow, SIEM/logs, Sigstore/SLSA (software artifacts, not physical decisions).

**Smallest demo:** Show a diagnosis, export an evidence packet, verify it offline; tamper with the model version or input hash and show verification fails; show an uncertain decision with an explicit refusal record.

**60–90s demo:** "An AI told a technician to replace a $40,000 bearing. Six months later, an auditor asks why. ProofLayer reconstructs the exact sensor window hash, model version, features, threshold, and human sign-off — offline. Change one field: the proof breaks."

**Hackathon scope:** Technically deep, but more infrastructure than user workflow; signing/verifier feasible; buyer unclear for a 36-hour demo.

**Risks:** Crowded AI-governance narrative; judges may see "blockchain for AI"; no customer; legal claims; crypto implementation risk; less emotional than a repair story.

**Invalidation:** Auditors say existing logs/model cards are sufficient; buyers will not pay separately for evidence; physical decision provenance is already solved by CMMS/condition-monitoring vendors.

---

## Candidate 4 — **Sentinel** (refine current product)

**Pitch:** Offline-first bearing condition monitoring for remote pumps and compressors, with a local verdict and a durable event trail.

**Exact user:** Reliability engineer at a remote water utility, mine, farm, or small plant with poor connectivity.

**Problem:** Remote rotating equipment fails without warning; cloud monitoring is unreliable or expensive; periodic routes miss developing faults.

**Workaround:** Monthly vibration routes, run-to-failure, expensive continuous-monitoring systems.

**Why now:** Cheap edge hardware and LoRa make local monitoring feasible.

**Input → transformation → output:** Vibration windows → local model → diagnostic summary over LoRa → dashboard/history.

**Existing capabilities:** Almost the entire repo.

**Built from scratch:** Product packaging, hardware, installation, multi-asset fleet management, alerting, support.

**Differentiation:** Offline/durable, low bandwidth, honest uncertainty. But this is the current product with a narrower vertical.

**Competitors:** Augury, Fluke, SKF, Emerson, Petasense, Hydro Centaur, countless PdM vendors.

**Smallest demo:** Current loopback demo.

**60–90s demo:** Network cut; local verdict still produced; event survives; dashboard reconciles.

**Hackathon scope:** Very feasible but not a radical pivot; novelty weak.

**Risks:** Crowded; no hardware; model narrow; judges see "another PdM dashboard."

**Invalidation:** A judge can name three incumbents doing the same thing; no unique workflow.

---

## Candidate 5 — **GateKeep**

**Pitch:** A deployment gate that proves an edge AI model is safe to run on a specific machine — or refuses to start it.

**Exact user:** ML platform engineer or reliability engineer deploying models to industrial edge devices.

**Problem:** Models silently run with the wrong feature order, sample rate, library version, or artifact; predictions look plausible but are invalid. Edge deployments are hard to test.

**Workaround:** Manual checklists, Docker pins, hope, post-hoc debugging.

**Why now:** Edge AI proliferation; model supply-chain security; regulated deployments.

**Input → transformation → output:** Model bundle + device contract + test windows → validation suite (hash, schema, feature order, sample rate, latency, OOD, calibration) → pass/fail report + signed deployment manifest.

**Existing capabilities:** Bundle validation, input contract, version checks, evaluation harness, edge inference.

**Built from scratch:** Test harness, device fingerprint, policy engine, report UI, CI integration.

**Differentiation:** Physical input contract + runtime device verification, not just model registry metadata.

**Competitors:** MLflow, model registries, Sigstore/SLSA, container signing, NannyML/Arize (monitoring), vendor-specific tools.

**Smallest demo:** Deploy a model with wrong sample rate/feature order; GateKeep rejects before it can produce a false healthy; correct model passes; signed manifest.

**60–90s demo:** "This model would have run. Watch it reject the bundle because the feature order is wrong — before a technician ever sees a diagnosis."

**Hackathon scope:** Feasible; technical judges like it; less user-facing.

**Risks:** Niche buyer; "why not just CI?"; no physical device; a judge may see it as a library feature.

**Invalidation:** Teams say model registries/CI already cover this; no willingness to pay for a separate gate.

---

## Candidate 6 — **WarrantyWitness**

**Pitch:** Sensor-backed evidence for equipment warranty claims — adjudicate faster, and reject claims the machine contradicts.

**Exact user:** Warranty administrator at an equipment OEM, extended-warranty provider, or fleet insurer.

**Problem:** Claims are decided on paperwork, photos, and dealer assertions; fraudulent or misdiagnosed claims are expensive; good claims are delayed. Manufacturers paid ~1.33% of product sales on warranty claims in 2024 (Warranty Week, Apr 2025; U.S.-based manufacturers), and appliance/HVAC claims alone were ~$1.28B.

**Workaround:** Manual adjusters, dealer trust, teardown inspections, claim rules.

**Why now:** Warranty costs and scrutiny; sensor data exists but is not used in adjudication.

**Input → transformation → output:** Claim + equipment history + vibration evidence → model/evidence review → approve/deny/request inspection, with audit record.

**Existing capabilities:** Diagnostic record, evidence, technician confirmation, cost estimate, history.

**Built from scratch:** Claims workflow, policy rules, integrations, fraud scoring, legal/compliance.

**Differentiation:** Physical evidence in the claims decision, not just documents.

**Competitors:** Warranty administration platforms (PCMI, Claimlane, Warranty Vision), OEM systems, adjusters.

**Smallest demo:** A claim says bearing failed; evidence says healthy/no fault; system flags for inspection; a valid claim passes.

**60–90s demo:** "This claim says the bearing failed at 200 hours. The vibration evidence says no damage. WarrantyWitness doesn't deny it — it requests the right inspection, with proof."

**Hackathon scope:** Feasible but requires policy/business logic; less visceral than repair closure; buyer access hard.

**Risks:** Legal/regulatory; adversarial incentives; no claims data; judge sees as insurance workflow, not AI.

**Invalidation:** Warranties are decided by contract terms, not sensor evidence; OEMs won't share data; privacy/liability.

---

## Candidate 7 — **CommonGround**

**Pitch:** A reproducible, leakage-audited benchmark for industrial vibration models — so "95% accuracy" means something.

**Exact user:** Industrial AI/ML team, academic lab, or CTO evaluating a condition-monitoring model.

**Problem:** Bearing-model papers report random-window accuracy, leak the same physical bearing across train/test, and ignore calibration/OOD. Buyers cannot compare vendors.

**Workaround:** Internal held-out sets, vendor claims, literature, expensive pilots.

**Why now:** Industrial AI is crowded; procurement needs evidence; model audits are rising.

**Input → transformation → output:** Model + dataset manifest → grouped split audit, leakage checks, calibration/OOD/latency evaluation → signed benchmark report.

**Existing capabilities:** Grouped split, evaluation metrics, bundle contract, Paderborn preparation.

**Built from scratch:** Benchmark harness, dataset registry, leaderboard, report UI, governance.

**Differentiation:** Physical-bearing-level leakage audit + deployment contract, not generic ML benchmarking.

**Competitors:** MLPerf, Papers with Code, Hugging Face, Kolena, Galileo, internal eval teams.

**Smallest demo:** Submit a model that scores 99% on random split; CommonGround shows it leaks bearings and scores 62% on held-out physical bearings.

**60–90s demo:** "This model claims 99%. One click shows it trained and tested on the same bearing. Real held-out score: 62%."

**Hackathon scope:** Feasible with existing code; dry demo; niche buyer.

**Risks:** Data access/licensing; benchmark adoption; "who pays?"; judges may find it meta.

**Invalidation:** Teams already use grouped splits; no willingness to pay for an external benchmark; data cannot be shared.

---

## Candidate 8 — **Echo**

**Pitch:** Point your phone at a broken appliance; hear what's wrong.

**Exact user:** Homeowner, appliance repair technician, property manager.

**Problem:** Appliance repair is expensive and opaque; diagnosis requires a technician visit.

**Workaround:** YouTube, guesswork, paid diagnostic visit.

**Why now:** Phones have microphones; consumers want instant answers.

**Input → transformation → output:** Phone audio/vibration recording → acoustic model → likely fault + next step.

**Existing capabilities:** Signal features, edge inference pattern, diagnostic record — but **not** the model, sample rate, or data.

**Built from scratch:** New acoustic dataset, new model, mobile capture, liability/regulatory handling.

**Differentiation:** Convenience; but "Shazam for broken appliances" is an obvious idea and technically unsupported here.

**Competitors:** Manufacturer apps, YouTube, repair marketplaces, acoustic diagnostic startups.

**Smallest demo:** Would require faking or a new dataset; not credible in the hackathon timeframe.

**60–90s demo:** Not credible without real acoustic data.

**Hackathon scope:** Reject. The current 64 kHz bearing model does not transfer to phone audio.

**Risks:** Fake AI, data mismatch, safety/liability, consumer trust.

**Invalidation:** No labeled acoustic data; model cannot generalize; demo would be staged.

---

## Candidate 9 — **Relay**

**Pitch:** Delay-tolerant evidence transport for remote infrastructure inspections — every event survives the network.

**Exact user:** Field operations lead at a remote mine, pipeline, or environmental monitoring program.

**Problem:** Remote sites lose connectivity; inspection evidence is lost, duplicated, or arrives late; auditors cannot trust the timeline.

**Workaround:** Paper forms, store-and-forward scripts, satellite bursts, manual reconciliation.

**Why now:** Cheap LoRa/edge devices; regulatory pressure for evidence.

**Input → transformation → output:** Compact evidence event → durable outbox → LoRa/gateway spool → idempotent API → auditable timeline.

**Existing capabilities:** Outbox, spool, protocol, event identity, idempotency — the strongest distributed-systems asset.

**Built from scratch:** Generic evidence schema, device identity, signing, field app, integrations.

**Differentiation:** Correct offline delivery semantics, not just a dashboard.

**Competitors:** Delay-tolerant networking stacks, IoT platforms, CMMS offline modes, message queues.

**Smallest demo:** Cut the network; capture events; show no loss/duplication after reconnect; tamper with a record and show detection.

**60–90s demo:** "The network is down. The event is already durable. Reconnect: exactly once, in order, verifiable."

**Hackathon scope:** Feasible; but it is infrastructure, not a user problem; judges may not see the value.

**Risks:** Developer-tool positioning; no domain; "why not MQTT/store-and-forward?"; less emotional.

**Invalidation:** Standard IoT platforms already provide durable delivery; no unique evidence layer.

---

## Candidate 10 — **Loop**

**Pitch:** Every technician confirmation makes the next diagnosis better — a field-calibrated diagnostic loop.

**Exact user:** Reliability team with a deployed vibration model and a backlog of uncertain diagnoses.

**Problem:** Models are static; field feedback is captured but not used; uncertain cases stay uncertain.

**Workaround:** Manual analyst review, periodic retraining, ignore feedback.

**Input → transformation → output:** Diagnostic + technician confirmation → calibration/active-learning update → improved decision policy.

**Existing capabilities:** Technician feedback endpoint, diagnostic record, feature pipeline, model bundle.

**Built from scratch:** Calibration method, retraining pipeline, active-learning queue, evaluation, governance.

**Differentiation:** Closes the loop from field outcome to model policy.

**Competitors:** MLOps/active-learning platforms, reliability services, vendor retraining.

**Smallest demo:** Show an uncertain case, technician confirms, calibration policy changes, next similar case is handled differently. But without enough data, this is easy to fake.

**Hackathon scope:** High risk of fake AI; calibration data absent; reject for this event.

**Risks:** No labels, no retraining data, overclaiming, data leakage.

**Invalidation:** Cannot demonstrate a real improvement on held-out data; feedback is too sparse.

---

## Summary table

| # | Candidate | Category | Primary user | Core loop | Causal fit to repo | Distinctness |
|---:|---|---|---|---|---|---|
| 1 | FixProof | Repair verification | Service/facility manager | Before/after → verdict → certificate | Very high | High |
| 2 | AssetPass | Condition passport | Used-equipment buyer/seller | Test → passport → verify | High | Medium |
| 3 | ProofLayer | AI decision audit | Industrial AI/audit team | Decision → evidence packet → verify | High | Medium-high |
| 4 | Sentinel | Predictive maintenance | Reliability engineer | Monitor → diagnose → alert | Very high | Low |
| 5 | GateKeep | Edge model assurance | ML platform engineer | Bundle → validation → deploy/refuse | High | Medium |
| 6 | WarrantyWitness | Warranty adjudication | Warranty administrator | Claim + evidence → decision | Medium-high | Medium |
| 7 | CommonGround | Benchmark/audit | Industrial AI team | Model + data → leakage audit | Medium | Medium |
| 8 | Echo | Consumer diagnosis | Homeowner/tech | Sound → fault | Low | Low (and unsupported) |
| 9 | Relay | Offline evidence transport | Remote operations lead | Event → durable relay → timeline | High | Medium |
| 10 | Loop | Field-calibrated AI | Reliability team | Feedback → calibration | Medium | Medium |

**Shortlist:** FixProof, ProofLayer, AssetPass. FixProof is the strongest intersection of user value, demo impact, reuse, and feasibility. ProofLayer is the runner-up if the hackathon is explicitly about AI trust/governance. AssetPass is the runner-up if the theme is circular economy/marketplace trust.
