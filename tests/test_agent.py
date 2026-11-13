from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from agent.planner import SNOOZE, apply_decision, assess, build_proposal, evaluate_asset, next_idle_window, record_finding, technician_worklist
from agent.registry import RegistryError, load_registry, validate_registry
from backend.main import MemoryStore, create_app

NOW = datetime(2026, 11, 12, 6, 0, tzinfo=timezone.utc)  # Thursday 11:30 IST

REGISTRY = {
    "schema_version": "axon-shop-registry-v1",
    "technicians": [{"technician_id": "tech-1", "name": "Technician One"}],
    "dealers": [{"dealer_id": "dealer-1", "name": "Dealer One"}],
    "shops": [
        {"shop_id": "shop-a", "name": "Shop A", "language": "en", "utc_offset_minutes": 330,
         "idle_windows": [{"weekday": "sunday", "start": "08:00", "end": "18:00"}],
         "technician_id": "tech-1", "dealer_id": "dealer-1",
         "assets": [{"asset_id": "loom-3", "label": "Loom 3", "parts": {"bearing-drive-end": {"description": "Drive-end bearing", "part_number": "6203"}}}]},
        {"shop_id": "shop-b", "name": "Shop B", "language": "hi", "utc_offset_minutes": 330, "idle_windows": [],
         "technician_id": "tech-1", "dealer_id": "dealer-1",
         "assets": [{"asset_id": "mill-1", "label": "Mill 1"}, {"asset_id": "pump-1", "label": "Pump 1"}]},
    ],
}


def event(status, age: timedelta, *, asset="loom-3", ratio=None):
    evidence = [] if ratio is None else [{"detector": "healthy_only_baseline", "drift_ratio": ratio,
                                          "changed_features": [{"feature": "kurtosis", "deviation": 9.0, "direction": "higher"}]}]
    return {"event_id": str(uuid4()), "timestamp": (NOW - age).isoformat(), "asset_id": asset, "component_id": "bearing-drive-end",
            "fault_class": "healthy" if status.startswith("HEALTHY") else "unknown", "fault_location": None, "confidence": None,
            "confidence_calibrated": False, "status": status, "evidence": evidence, "alternative_hypotheses": [],
            "missing_information": [], "recommended_confirmation_tests": [], "repair_reference_ids": [], "cost_estimate_id": None,
            "model_version": "axon-healthy-baseline-test", "requires_technician_confirmation": status == "FAULT_SUSPECTED", "simulated": False}


def drifting_history(days=4, ratio=1.2):
    """Newest first: a machine that drifted `days` ago after running normally."""
    suspected = [event("FAULT_SUSPECTED", timedelta(days=days) * index / 5, ratio=ratio) for index in range(6)]
    healthy = [event("HEALTHY_WITHIN_VALIDATED_SCOPE", timedelta(days=days + 1 + index)) for index in range(4)]
    return suspected + healthy


def test_one_unusual_window_is_not_a_warning():
    history = [event("FAULT_SUSPECTED", timedelta(hours=1), ratio=2.0)] + [event("HEALTHY_WITHIN_VALIDATED_SCOPE", timedelta(hours=2 + index)) for index in range(6)]
    assert assess(history, NOW) is None
    assert evaluate_asset(REGISTRY, "loom-3", history, [], NOW) == ("no_warning", None)


def test_persistent_drift_becomes_a_plain_language_proposal_in_an_idle_window():
    action, proposal = evaluate_asset(REGISTRY, "loom-3", drifting_history(), [], NOW)
    assert action == "proposal_created" and proposal["state"] == "awaiting_owner" and proposal["urgency"] == "urgent"
    text = proposal["owner_message"]["text"]
    assert text.startswith("Loom 3: the motor-side bearing") and "4 days" in text and "sharp knocks" in text and "Sunday 15 Nov" in text
    assert proposal["proposed_slot"]["weekday"] == "sunday" and proposal["proposed_slot"]["start"].startswith("2026-11-15T08:00")
    assert [step["state"] for step in proposal["steps"]] == ["awaiting_owner_approval"] * 2
    assert "6203" in proposal["steps"][1]["draft"] and proposal["steps"][0]["recipient_name"] == "Technician One"
    assert proposal["policy"]["machine_control"] == "never"


def test_owner_message_follows_the_shop_language_and_missing_idle_time():
    history = [dict(item, asset_id="mill-1") for item in drifting_history(days=1, ratio=1.1)]
    _, proposal = evaluate_asset(REGISTRY, "mill-1", history, [], NOW)
    assert proposal["owner_message"]["language"] == "hi" and "मिस्त्री" in proposal["owner_message"]["text"]
    assert proposal["proposed_slot"] is None and proposal["urgency"] == "soon"


def test_idle_window_skips_one_that_has_already_ended():
    shop = {"utc_offset_minutes": 330, "idle_windows": [{"weekday": "thursday", "start": "06:00", "end": "09:00"}]}
    assert next_idle_window(shop, NOW)["start"].startswith("2026-11-19T06:00")


def test_owner_approves_step_by_step_and_not_now_is_raised_again_later():
    history = drifting_history()
    _, proposal = evaluate_asset(REGISTRY, "loom-3", history, [], NOW)
    apply_decision(proposal, "request_technician", "approve", "owner", NOW)
    assert proposal["state"] == "approved" and proposal["steps"][1]["state"] == "awaiting_owner_approval"
    assert evaluate_asset(REGISTRY, "loom-3", history, [proposal], NOW)[0] == "proposal_open"
    apply_decision(proposal, "all", "not_now", "owner", NOW)
    assert proposal["state"] == "deferred"
    assert evaluate_asset(REGISTRY, "loom-3", history, [proposal], NOW + timedelta(hours=1))[0] == "proposal_open"
    action, raised = evaluate_asset(REGISTRY, "loom-3", history, [proposal], NOW + SNOOZE)
    assert action == "proposal_raised_again" and raised["proposal_id"] == proposal["proposal_id"] and raised["state"] == "awaiting_owner"
    with pytest.raises(ValueError):
        apply_decision(proposal, "stop_machine", "approve", "owner", NOW)


def test_technician_finding_closes_the_episode_and_feeds_the_baseline():
    history = drifting_history()
    _, proposal = evaluate_asset(REGISTRY, "loom-3", history, [], NOW)
    record_finding(proposal, "tech-1", "no_fault_found", "bearing is fine", NOW)
    assert proposal["state"] == "closed"
    assert proposal["technician_finding"]["baseline_feedback"]["action"] == "add_flagged_windows_to_healthy_reference"
    assert evaluate_asset(REGISTRY, "loom-3", history, [proposal], NOW + timedelta(minutes=1))[0] == "no_warning"
    with pytest.raises(ValueError, match="closed"):
        apply_decision(proposal, "all", "approve", "owner", NOW)


def test_worklist_ranks_machines_across_shops():
    urgent = build_proposal(REGISTRY, "loom-3", assess(drifting_history(), NOW), NOW)
    soon = build_proposal(REGISTRY, "mill-1", assess(drifting_history(days=1, ratio=1.1), NOW), NOW)
    apply_decision(urgent, "request_technician", "approve", "owner", NOW)
    latest = {"loom-3": event("FAULT_SUSPECTED", timedelta(0)), "mill-1": event("FAULT_SUSPECTED", timedelta(0)), "pump-1": None}
    rows = technician_worklist(REGISTRY, "tech-1", latest, {"loom-3": [urgent], "mill-1": [soon]})
    assert [(row["rank"], row["asset_id"], row["attention"]) for row in rows] == [(1, "loom-3", "urgent"), (2, "mill-1", "plan_repair"), (3, "pump-1", "no_data")]
    assert rows[0]["owner_approved_visit"] and not rows[1]["owner_approved_visit"] and rows[0]["shop_name"] == "Shop A"
    assert technician_worklist(REGISTRY, "someone-else", latest, {}) == []


def test_registry_validation_and_packaged_example():
    with pytest.raises(RegistryError, match="schema_version"):
        validate_registry({"shops": []})
    broken = {**REGISTRY, "shops": [dict(REGISTRY["shops"][0], technician_id="missing")]}
    with pytest.raises(RegistryError, match="unknown technician_id"):
        validate_registry(broken)
    example = load_registry()
    assert example["shops"] and example["example_data"] is True


def test_api_agent_flow_from_ingest_to_technician_finding():
    client = TestClient(create_app(store=MemoryStore(), registry=REGISTRY))
    live = datetime.now(timezone.utc)
    actions = []
    for index in range(3):
        payload = event("FAULT_SUSPECTED", timedelta(0), ratio=1.3) | {"timestamp": (live - timedelta(minutes=3 - index)).isoformat()}
        actions.append(client.post("/ingest/diagnostic", json=payload).json()["agent"])
    assert actions == ["no_warning", "no_warning", "proposal_created"]
    unregistered = event("FAULT_SUSPECTED", timedelta(0), asset="unknown-machine") | {"timestamp": live.isoformat()}
    assert client.post("/ingest/diagnostic", json=unregistered).json()["agent"] == "asset_not_registered"
    proposals = client.get("/agent/proposals").json()
    assert len(proposals) == 1 and proposals[0]["asset_id"] == "loom-3"
    proposal_id = proposals[0]["proposal_id"]
    assert client.post("/agent/evaluate", json={"asset_id": "loom-3"}).json()["action"] == "proposal_open"
    approved = client.post(f"/agent/proposals/{proposal_id}/decision", json={"step": "request_technician", "decision": "approve"}).json()
    assert approved["state"] == "approved"
    assert client.post(f"/agent/proposals/{proposal_id}/decision", json={"step": "shutdown", "decision": "approve"}).status_code == 422
    worklist = client.get("/technician/worklist", params={"technician_id": "tech-1"}).json()["machines"]
    assert worklist[0]["asset_id"] == "loom-3" and worklist[0]["owner_approved_visit"] and len(worklist) == 3
    closed = client.post(f"/agent/proposals/{proposal_id}/finding", json={"technician_id": "tech-1", "finding": "repaired"}).json()
    assert closed["state"] == "closed" and closed["technician_finding"]["baseline_feedback"]["action"] == "refit_baseline_after_repair"
    assert client.get("/agent/proposals").json() == [] and len(client.get("/agent/proposals", params={"include_closed": True}).json()) == 1
    assert client.post(f"/agent/proposals/{proposal_id}/finding", json={"technician_id": "tech-1", "finding": "repaired"}).status_code == 409
    assert client.post("/agent/proposals/missing/decision", json={"decision": "approve"}).status_code == 404
    assert client.post("/command", json={"machine_id": "loom-3", "action": "shutdown"}).status_code == 501
