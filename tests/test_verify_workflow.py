"""End-to-end repair verification journey against the real deployed model.

Every verdict below comes from genuine model output on the packaged Paderborn
windows, not from stubbed probabilities:

* KA04 is a documented damaged bearing the model scores as damage with
  confidence 1.0, so it establishes a fault baseline.
* K003 is a documented healthy bearing (held out of training) the model scores
  as healthy with confidence 1.0, so it closes a repair.
* KI04 is a documented damaged bearing the model cannot separate from healthy,
  which is what real uncertainty looks like.
"""
from __future__ import annotations

import pytest

from verify_helpers import (
    auth,
    bootstrap_tenant,
    capture_replay,
    register,
    start_repair,
    start_work_order,
)

DAMAGED = "N09_M07_F10_KA04_1"   # training bearing, documented damage
HEALTHY = "N09_M07_F10_K003_1"   # held-out bearing, documented healthy
AMBIGUOUS = "N09_M07_F10_KI04_1"  # held-out bearing, model is genuinely unsure


@pytest.fixture()
def journey(client):
    """Owner plus a ready work order and repair session."""
    session = register(client, "owner@acme.test", "Acme Industrial Services")
    tenant = bootstrap_tenant(client, session)
    order = start_work_order(client, tenant)
    repair = start_repair(client, order["id"], tenant["headers"])
    return {"session": session, "tenant": tenant, "order": order, "repair": repair,
            "headers": tenant["headers"]}


# ------------------------------------------------------------- happy path


def test_full_journey_produces_a_verified_certificate(client, journey):
    repair_id = journey["repair"]["id"]
    headers = journey["headers"]

    before = capture_replay(client, repair_id, headers, "before", DAMAGED)
    assert before["diagnostic"]["status"] == "FAULT_SUSPECTED"
    assert before["diagnostic"]["confidence"] == pytest.approx(1.0)
    assert before["repair"]["status"] == "awaiting_after"

    after = capture_replay(client, repair_id, headers, "after", HEALTHY)
    assert after["diagnostic"]["status"] == "HEALTHY_WITHIN_VALIDATED_SCOPE"
    assert after["repair"]["status"] == "awaiting_verification"

    verified = client.post(f"/v1/repairs/{repair_id}/verify", headers=headers).json()
    assert verified["result"]["verdict"] == "VERIFIED"
    assert verified["result"]["comparability"]["comparable"] is True
    assert verified["repair"]["verdict"] == "VERIFIED"

    issued = client.post(f"/v1/repairs/{repair_id}/certificate", headers=headers)
    assert issued.status_code == 201, issued.text
    certificate = issued.json()["certificate"]
    payload = certificate["payload"]

    assert payload["verdict"] == "VERIFIED"
    assert payload["asset"]["name"] == "Pump P-101"
    assert payload["input_contract"]["model_version"]
    assert payload["input_contract"]["confidence_calibrated"] is False
    assert payload["policy"]["policy_version"] == "axv-policy-v1"
    assert payload["before"]["evidence_sha256"].startswith("sha256:")
    assert payload["after"]["reading_sha256"].startswith("sha256:")
    assert "not a legal certification" in payload["scope"]
    # Replayed laboratory evidence must be disclosed on the certificate itself.
    assert payload["before"]["simulated"] is True
    assert payload["after"]["simulated"] is True

    certificate_id = certificate["id"]
    public = client.get(f"/v1/public/certificates/{certificate_id}")
    assert public.status_code == 200
    assert public.json()["valid"] is True
    assert public.json()["payload"]["verdict"] == "VERIFIED"

    report = client.get(f"/v1/public/certificates/{certificate_id}/report")
    assert report.status_code == 200
    assert "Repair verification record" in report.text
    assert "Uncalibrated confidence" in report.text
    assert "Evidence source disclosure" in report.text
    assert "CC BY-NC 4.0" in report.text

    offline = client.get("/v1/public/keys").json()["keys"]
    assert offline[0]["algorithm"] == "Ed25519"

    stats = client.get("/v1/stats", headers=headers).json()
    assert stats["verified_repairs"] == 1
    assert stats["certificates"] == 1
    assert stats["confidence_calibrated"] is False


def test_a_second_certificate_for_the_same_repair_is_refused(client, journey):
    repair_id = journey["repair"]["id"]
    headers = journey["headers"]
    capture_replay(client, repair_id, headers, "before", DAMAGED)
    capture_replay(client, repair_id, headers, "after", HEALTHY)
    client.post(f"/v1/repairs/{repair_id}/verify", headers=headers)
    assert client.post(f"/v1/repairs/{repair_id}/certificate",
                       headers=headers).status_code == 201
    assert client.post(f"/v1/repairs/{repair_id}/certificate",
                       headers=headers).status_code == 409


# --------------------------------------------------------- negative journeys


def test_failed_repair_is_not_verified(client, journey):
    """The repair did not clear the fault: the platform must say so."""
    repair_id = journey["repair"]["id"]
    headers = journey["headers"]
    capture_replay(client, repair_id, headers, "before", DAMAGED)
    capture_replay(client, repair_id, headers, "after", DAMAGED, window_index=1)

    verified = client.post(f"/v1/repairs/{repair_id}/verify", headers=headers).json()
    assert verified["result"]["verdict"] == "NOT_VERIFIED"
    codes = [reason["code"] for reason in verified["result"]["reasons"]]
    assert "AFTER_STILL_FAULT" in codes

    issued = client.post(f"/v1/repairs/{repair_id}/certificate", headers=headers)
    assert issued.status_code == 201
    assert issued.json()["certificate"]["payload"]["verdict"] == "NOT_VERIFIED"


def test_uncertain_evidence_produces_an_inconclusive_verdict(client, journey):
    """KI04 is a damaged bearing the model cannot separate from healthy."""
    repair_id = journey["repair"]["id"]
    headers = journey["headers"]
    capture_replay(client, repair_id, headers, "before", DAMAGED)
    after = capture_replay(client, repair_id, headers, "after", AMBIGUOUS)
    assert after["diagnostic"]["status"] == "DIAGNOSIS_UNCERTAIN"

    verified = client.post(f"/v1/repairs/{repair_id}/verify", headers=headers).json()
    assert verified["result"]["verdict"] == "INCONCLUSIVE"
    codes = [reason["code"] for reason in verified["result"]["reasons"]]
    assert codes == ["AFTER_UNCERTAIN"]


def test_model_unavailability_blocks_verification(client, journey, monkeypatch, tmp_path):
    monkeypatch.setenv("AXON_BEARING_MODEL_DIR", str(tmp_path / "no-model-here"))
    repair_id = journey["repair"]["id"]
    headers = journey["headers"]

    status = client.get("/v1/model-status", headers=headers).json()
    assert status["available"] is False
    assert status["confidence_calibrated"] is False

    before = client.post(f"/v1/repairs/{repair_id}/capture", json={
        "phase": "before", "source": "replay", "recording_id": DAMAGED,
        "window_index": 0}, headers=headers).json()
    assert before["diagnostic"]["status"] == "MODEL_UNAVAILABLE"
    capture_replay(client, repair_id, headers, "after", HEALTHY)

    verified = client.post(f"/v1/repairs/{repair_id}/verify", headers=headers).json()
    assert verified["result"]["verdict"] == "CANNOT_VERIFY"
    codes = [reason["code"] for reason in verified["result"]["reasons"]]
    assert "MODEL_UNAVAILABLE" in codes


def test_captureing_one_phase_twice_is_refused(client, journey):
    repair_id = journey["repair"]["id"]
    headers = journey["headers"]
    capture_replay(client, repair_id, headers, "before", DAMAGED)
    conflict = client.post(f"/v1/repairs/{repair_id}/capture", json={
        "phase": "before", "source": "replay", "recording_id": DAMAGED,
        "window_index": 0}, headers=headers)
    assert conflict.status_code == 409
    assert "already been captured" in conflict.json()["detail"]


def test_verification_requires_both_phases(client, journey):
    repair_id = journey["repair"]["id"]
    headers = journey["headers"]
    capture_replay(client, repair_id, headers, "before", DAMAGED)
    blocked = client.post(f"/v1/repairs/{repair_id}/verify", headers=headers)
    assert blocked.status_code == 409
    assert "after" in blocked.json()["detail"]


def test_certificate_requires_a_verdict_first(client, journey):
    repair_id = journey["repair"]["id"]
    headers = journey["headers"]
    capture_replay(client, repair_id, headers, "before", DAMAGED)
    capture_replay(client, repair_id, headers, "after", HEALTHY)
    refused = client.post(f"/v1/repairs/{repair_id}/certificate", headers=headers)
    assert refused.status_code == 409
    assert "verify" in refused.json()["detail"].lower()


def test_unknown_recordings_are_refused(client, journey):
    repair_id = journey["repair"]["id"]
    response = client.post(f"/v1/repairs/{repair_id}/capture", json={
        "phase": "before", "source": "replay", "recording_id": "DOES_NOT_EXIST",
        "window_index": 0}, headers=journey["headers"])
    assert response.status_code == 409


# ------------------------------------------------------------ evidence rules


def test_uploaded_windows_are_scored_and_marked_as_uploads(client, journey):
    from backend.paderborn_replay import read_window
    repair_id = journey["repair"]["id"]
    headers = journey["headers"]
    _, signal, sampling_frequency = read_window(DAMAGED, 0)

    captured = client.post(f"/v1/repairs/{repair_id}/capture", json={
        "phase": "before", "source": "upload",
        "signal": [round(float(value), 6) for value in signal.tolist()],
        "sampling_frequency_hz": sampling_frequency,
        "operating_condition_id": "N09_M07_F10"}, headers=headers).json()
    assert captured["diagnostic"]["status"] == "FAULT_SUSPECTED"
    assert captured["repair"]["before"]["reading"]["source"] == "upload"
    assert captured["repair"]["before"]["reading"]["sha256"].startswith("sha256:")


def test_a_window_that_violates_the_input_contract_is_recorded_as_invalid(client, journey):
    repair_id = journey["repair"]["id"]
    headers = journey["headers"]
    captured = client.post(f"/v1/repairs/{repair_id}/capture", json={
        "phase": "before", "source": "upload", "signal": [0.1] * 128,
        "sampling_frequency_hz": 64000}, headers=headers).json()
    assert captured["diagnostic"]["status"] == "SENSOR_DATA_INVALID"


def test_non_finite_samples_are_rejected_at_the_edge(client, journey):
    """A client that literally sends NaN or Infinity must get a 422, not a 500.

    The raw body is sent by hand because JSON encoders (httpx included) refuse
    to serialise non-finite floats at all.
    """
    repair_id = journey["repair"]["id"]
    headers = {**journey["headers"], "Content-Type": "application/json"}
    for token in ("NaN", "Infinity", "-Infinity"):
        body = ('{"phase": "before", "source": "upload", "sampling_frequency_hz": 64000, '
                f'"signal": [{", ".join([token] * 32)}]}}')
        response = client.post(f"/v1/repairs/{repair_id}/capture", content=body,
                               headers=headers)
        assert response.status_code == 422, token
        assert "non-finite" in response.text

    rejected = client.post("/v1/readings", content=(
        '{"asset_id": "%s", "component_id": "%s", "sampling_frequency_hz": 64000, '
        '"signal": [%s]}' % (journey["tenant"]["asset"]["id"],
                             journey["tenant"]["component"]["id"],
                             ", ".join(["NaN"] * 32))), headers=headers)
    assert rejected.status_code == 422


def test_operating_condition_mismatch_makes_the_evidence_non_comparable(client, journey):
    repair_id = journey["repair"]["id"]
    headers = journey["headers"]
    capture_replay(client, repair_id, headers, "before", DAMAGED)
    client.post(f"/v1/repairs/{repair_id}/capture", json={
        "phase": "after", "source": "replay", "recording_id": HEALTHY,
        "window_index": 0, "operating_condition_id": "N15_M07_F10"}, headers=headers)

    verified = client.post(f"/v1/repairs/{repair_id}/verify", headers=headers).json()
    assert verified["result"]["verdict"] == "INCONCLUSIVE"
    codes = [reason["code"] for reason in verified["result"]["reasons"]]
    assert "OPERATING_CONDITION_MISMATCH" in codes
    assert verified["result"]["comparability"]["operating_condition_match"] is False


# -------------------------------------------------------------- tamper proof


def test_a_tampered_certificate_is_rejected_by_the_public_endpoint(client, journey):
    from backend.verify_store import VerifyStore
    repair_id = journey["repair"]["id"]
    headers = journey["headers"]
    capture_replay(client, repair_id, headers, "before", DAMAGED)
    capture_replay(client, repair_id, headers, "after", HEALTHY)
    client.post(f"/v1/repairs/{repair_id}/verify", headers=headers)
    certificate = client.post(f"/v1/repairs/{repair_id}/certificate", headers=headers).json()
    certificate_id = certificate["certificate"]["id"]

    app = client.app
    store: VerifyStore = app.state.verify_store
    row = store.find_certificate(certificate_id)
    row["payload"]["verdict"] = "NOT_VERIFIED"
    store._execute("UPDATE certificates SET payload=? WHERE id=?",
                   (store._json(row["payload"]), certificate_id))

    tampered = client.get(f"/v1/public/certificates/{certificate_id}")
    assert tampered.status_code == 409
    assert tampered.json()["valid"] is False

    report = client.get(f"/v1/public/certificates/{certificate_id}/report")
    assert "verification FAILED" in report.text


def test_public_endpoints_never_expose_organisational_data(client, journey):
    repair_id = journey["repair"]["id"]
    headers = journey["headers"]
    capture_replay(client, repair_id, headers, "before", DAMAGED)
    capture_replay(client, repair_id, headers, "after", HEALTHY)
    client.post(f"/v1/repairs/{repair_id}/verify", headers=headers)
    certificate_id = client.post(f"/v1/repairs/{repair_id}/certificate",
                                 headers=headers).json()["certificate"]["id"]

    document = client.get(f"/v1/public/certificates/{certificate_id}").json()
    blob = str(document).lower()
    assert "owner@acme.test" not in blob
    assert "org_" not in blob, "internal organisation ids must not be published"
    assert "usr_" not in blob, "internal user ids must not be published"


def test_an_unknown_certificate_id_is_not_found(client):
    assert client.get("/v1/public/certificates/AXV-NOPE").status_code == 404
    assert client.get("/v1/public/certificates/AXV-NOPE/report").status_code == 404


# ------------------------------------------------------------------ timeline


def test_the_asset_timeline_records_evidence_and_repairs(client, journey):
    repair_id = journey["repair"]["id"]
    headers = journey["headers"]
    asset_id = journey["tenant"]["asset"]["id"]
    capture_replay(client, repair_id, headers, "before", DAMAGED)
    capture_replay(client, repair_id, headers, "after", HEALTHY)

    timeline = client.get(f"/v1/assets/{asset_id}/timeline", headers=headers).json()["events"]
    kinds = {event["kind"] for event in timeline}
    assert kinds == {"diagnostic", "repair"}
    replayed = [event for event in timeline if event["kind"] == "diagnostic"]
    assert all(event["simulated"] for event in replayed)
    assert all(event["confidence_calibrated"] is False for event in replayed)


def test_audit_log_records_the_verdict_and_its_reasons(client, journey):
    repair_id = journey["repair"]["id"]
    headers = journey["headers"]
    capture_replay(client, repair_id, headers, "before", DAMAGED)
    capture_replay(client, repair_id, headers, "after", HEALTHY)
    client.post(f"/v1/repairs/{repair_id}/verify", headers=headers)

    events = client.get("/v1/audit", headers=headers).json()["events"]
    actions = [event["action"] for event in events]
    assert "repair.before_captured" in actions
    assert "repair.after_captured" in actions
    assert "repair.verified" in actions
    verified = next(event for event in events if event["action"] == "repair.verified")
    assert verified["metadata"]["verdict"] == "VERIFIED"
    assert "AFTER_HEALTHY" in verified["metadata"]["reasons"]
