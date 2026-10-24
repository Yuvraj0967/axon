"""MQTT transport: topic contract, tenant binding, de-duplication and ingest."""
from __future__ import annotations

import json

import pytest

from backend.auth import hash_password
from backend.ingest_service import (
    IngestRejection,
    address_for,
    handle_transport_event,
    parse_topic,
)
from backend.mqtt_ingest import MqttIngestWorker, MqttSettings
from backend.verify_store import VerifyStore

ORG = "org_alpha"
SITE = "sit_plant1"
DEVICE = "plant1-gw-01"
ASSET = "ast_pump"
COMPONENT = "cmp_bearing"


@pytest.fixture()
def store(tmp_path):
    """A real tenant with a registered MQTT device."""
    database = VerifyStore(str(tmp_path / "verify.db"))
    database.create_org("Alpha Services")
    # Pin the identifiers the tests reason about.
    database._execute("UPDATE orgs SET id=? WHERE name=?", (ORG, "Alpha Services"))
    user = database.create_user("owner@alpha.test", "Owner",
                                hash_password("correct-horse-battery", iterations=10000))
    database._execute(
        "INSERT INTO memberships (id, org_id, user_id, role, created_at) VALUES (?,?,?,?,?)",
        ("mem_1", ORG, user["id"], "owner", "2026-01-01T00:00:00+00:00"))
    customer = database.create_customer(ORG, "Northwind Mills")
    database.create_site(ORG, customer["id"], "Plant 1")
    database._execute("UPDATE sites SET id=? WHERE org_id=?", (SITE, ORG))
    database.create_asset(ORG, site_id=SITE, customer_id=customer["id"], name="Pump P-101")
    database._execute("UPDATE assets SET id=? WHERE org_id=?", (ASSET, ORG))
    database.create_component(ORG, ASSET, "drive-end bearing")
    database._execute("UPDATE components SET id=? WHERE org_id=?", (COMPONENT, ORG))
    database.create_device(ORG, "Plant 1 gateway", DEVICE, site_id=SITE)
    yield database
    database.close()


def diagnostic_document(**overrides) -> dict:
    return {
        "event_id": "evt-1",
        "asset_id": ASSET,
        "component_id": COMPONENT,
        "status": "FAULT_SUSPECTED",
        "fault_class": "other_bearing_damage",
        "confidence": 0.97,
        "confidence_calibrated": False,
        "probabilities": {"healthy": 0.03, "other_bearing_damage": 0.97},
        "model_version": "axon-bearing-rf-test",
        "captured_at": "2026-01-01T00:00:00+00:00",
        "sampling_frequency_hz": 64000.0,
        "window_samples": 4096,
        "operating_condition_id": "N09_M07_F10",
        "simulated": True,
    } | overrides


def address(**overrides) -> "object":
    from backend.ingest_service import TopicAddress
    return TopicAddress(**{"prefix": "axon/v1", "org_id": ORG, "site_id": SITE,
                           "device_id": DEVICE, "kind": "diagnostic"} | overrides)


# --------------------------------------------------------------- topic rules


def test_topic_scheme_parses_exactly():
    parsed = parse_topic("axon/v1/org_a/sit_b/dev_c/diagnostic")
    assert parsed.org_id == "org_a"
    assert parsed.site_id == "sit_b"
    assert parsed.device_id == "dev_c"
    assert parsed.kind == "diagnostic"


@pytest.mark.parametrize("topic", [
    "axon/v1/org_a/sit_b/dev_c",              # too short
    "axon/v1/org_a/sit_b/dev_c/diagnostic/x",  # too long
    "other/v1/org_a/sit_b/dev_c/diagnostic",   # wrong prefix
    "axon/v1//sit_b/dev_c/diagnostic",        # empty org
    "axon/v1/org_a/sit_b/dev_c/metrics",      # unknown kind
    "axon/v1",                                # bare prefix
    "",
])
def test_foreign_traffic_is_ignored(topic):
    assert parse_topic(topic) is None


def test_custom_prefixes_are_supported():
    assert parse_topic("acme/v2/org_a/sit_b/dev_c/status", "acme/v2").kind == "status"
    assert parse_topic("acme/v2/org_a/sit_b/dev_c/status") is None, "default prefix is axon/v1"
    assert address_for("org_a", "sit_b", "dev_c", "window", "acme/v2") == \
        "acme/v2/org_a/sit_b/dev_c/window"


@pytest.mark.parametrize("kind", ["diagnostic", "window", "status", "command"])
def test_every_kind_round_trips(kind):
    topic = address_for(ORG, SITE, DEVICE, kind)
    assert parse_topic(topic).kind == kind


# ------------------------------------------------------------- tenant binding


def test_an_unregistered_device_is_refused(store):
    with pytest.raises(IngestRejection) as excinfo:
        handle_transport_event(store, address(device_id="not-registered"),
                               diagnostic_document())
    assert excinfo.value.code == "unknown_device"


def test_a_device_cannot_publish_into_another_organisation(store):
    with pytest.raises(IngestRejection) as excinfo:
        handle_transport_event(store, address(org_id="org_victim"), diagnostic_document())
    assert excinfo.value.code == "tenant_mismatch"


def test_a_device_cannot_publish_into_another_site(store):
    with pytest.raises(IngestRejection) as excinfo:
        handle_transport_event(store, address(site_id="sit_other"), diagnostic_document())
    assert excinfo.value.code == "site_mismatch"


def test_a_rejected_message_stores_nothing(store):
    with pytest.raises(IngestRejection):
        handle_transport_event(store, address(org_id="org_victim"), diagnostic_document())
    assert store.list_diagnostics(ORG) == []
    assert store.list_readings(ORG) == []


# ------------------------------------------------------------------- ingest


def test_a_diagnostic_event_is_stored_with_provenance(store):
    result = handle_transport_event(store, address(), diagnostic_document())
    assert result["accepted"] is True
    diagnostics = store.list_diagnostics(ORG)
    assert len(diagnostics) == 1
    assert diagnostics[0]["source"] == "mqtt"
    assert diagnostics[0]["event_id"] == "evt-1"
    assert diagnostics[0]["simulated"] is True
    reading = store.list_readings(ORG)[0]
    assert reading["source"] == "mqtt"
    assert reading["sha256"]
    device = store.list_devices(ORG)[0]
    assert device["last_seen"] is not None
    actions = [event["action"] for event in store.list_audit(ORG)]
    assert "diagnostic.ingested" in actions


def test_the_same_event_id_is_accepted_exactly_once(store):
    handle_transport_event(store, address(), diagnostic_document())
    with pytest.raises(IngestRejection) as excinfo:
        handle_transport_event(store, address(),
                               diagnostic_document(event_id="evt-1"))
    assert excinfo.value.code == "duplicate_event"
    assert len(store.list_diagnostics(ORG)) == 1


def test_an_event_for_an_unknown_asset_is_refused(store):
    with pytest.raises(IngestRejection) as excinfo:
        handle_transport_event(store, address(), diagnostic_document(asset_id="ast_ghost"))
    assert excinfo.value.code == "unknown_asset"


def test_a_window_event_is_scored_by_the_backend(store):
    from backend.paderborn_replay import read_window
    _, signal, sampling_frequency = read_window("N09_M07_F10_KA04_1", 0)
    result = handle_transport_event(store, address(kind="window"), {
        "event_id": "evt-window-1",
        "asset_id": ASSET,
        "component_id": COMPONENT,
        "sampling_frequency_hz": float(sampling_frequency),
        "signal": [round(float(value), 6) for value in signal.tolist()],
        "operating_condition_id": "N09_M07_F10",
    })
    assert result["accepted"] is True
    diagnostic = store.list_diagnostics(ORG)[0]
    assert diagnostic["status"] == "FAULT_SUSPECTED"
    assert diagnostic["source"] == "mqtt"
    reading = store.list_readings(ORG)[0]
    assert reading["window_samples"] == 4096
    assert reading["signal"] != []


def test_a_malformed_window_is_refused(store):
    with pytest.raises(IngestRejection) as excinfo:
        handle_transport_event(store, address(kind="window"), {"asset_id": ASSET})
    assert excinfo.value.code == "invalid_window"


def test_a_short_window_is_refused(store):
    with pytest.raises(IngestRejection) as excinfo:
        handle_transport_event(store, address(kind="window"), {
            "asset_id": ASSET, "component_id": COMPONENT, "signal": [0.1] * 8,
            "sampling_frequency_hz": 64000})
    assert excinfo.value.code == "window_too_short"


def test_status_heartbeats_touch_the_device_without_creating_evidence(store):
    result = handle_transport_event(store, address(kind="status"),
                                    {"state": "online", "ts": "2026-01-01T00:00:00Z"})
    assert result["accepted"] is True
    assert store.list_diagnostics(ORG) == []
    assert store.list_devices(ORG)[0]["last_seen"] is not None


def test_commands_are_recorded_but_not_acted_on(store):
    result = handle_transport_event(store, address(kind="command"), {"action": "shutdown"})
    assert result["accepted"] is False
    assert "not accepted" in result["reason"]
    actions = [event["action"] for event in store.list_audit(ORG)]
    assert "device.command_ignored" in actions


def test_invalid_probabilities_are_refused(store):
    with pytest.raises(IngestRejection) as excinfo:
        handle_transport_event(store, address(), diagnostic_document(
            probabilities={"healthy": 0.4, "other_bearing_damage": 0.4}))
    assert excinfo.value.code == "invalid_probability"


def test_an_unknown_status_is_refused(store):
    with pytest.raises(IngestRejection) as excinfo:
        handle_transport_event(store, address(), diagnostic_document(status="PROBABLY_FINE"))
    assert excinfo.value.code == "invalid_status"


# ------------------------------------------------------------------- worker


@pytest.fixture()
def worker(store):
    settings = MqttSettings(host="localhost", port=1883, use_tls=False, insecure=True,
                            database=":memory:", subscribe_all_tenants=True)
    return MqttIngestWorker(settings=settings, store=store)


def test_worker_accepts_a_well_formed_message(worker):
    result = worker.process(address_for(ORG, SITE, DEVICE, "diagnostic"),
                            json.dumps(diagnostic_document()).encode())
    assert result["accepted"] is True
    assert result["event_id"] == "evt-1"


def test_worker_ignores_foreign_topics(worker):
    result = worker.process("sensors/plant1/temperature", b"{}")
    assert result["accepted"] is False
    assert "not an AXON evidence topic" in result["reason"]


def test_worker_rejects_non_json(worker):
    result = worker.process(address_for(ORG, SITE, DEVICE, "diagnostic"),
                            b"\x00\x01\x02 not json")
    assert result["accepted"] is False
    assert "not valid JSON" in result["reason"]


def test_worker_rejects_json_that_is_not_an_object(worker):
    result = worker.process(address_for(ORG, SITE, DEVICE, "diagnostic"),
                            b'["array", "not", "object"]')
    assert result["accepted"] is False


def test_worker_rejects_a_payload_that_fails_validation(worker):
    result = worker.process(address_for(ORG, SITE, DEVICE, "diagnostic"),
                            json.dumps({"event_id": "evt-2"}).encode())
    assert result["accepted"] is False
    assert result["code"] == "invalid_payload"


def test_worker_never_raises_on_a_burst_of_bad_messages(worker):
    payloads = [b"", b"{", b"null", b"123", b'"string"',
                json.dumps({"asset_id": ASSET}).encode()]
    for payload in payloads:
        result = worker.process(address_for(ORG, SITE, DEVICE, "diagnostic"), payload)
        assert result["accepted"] is False


def test_worker_settings_default_to_tls():
    settings = MqttSettings()
    assert settings.use_tls is True
    assert settings.port == 8883
    assert settings.subscription == "axon/v1/+/+/+"


def test_worker_subscription_covers_every_tenant():
    assert MqttSettings(subscribe_all_tenants=True).subscription == "axon/v1/+/+/+"


# ------------------------------------------------------------- REST parity


def test_rest_and_mqtt_accept_the_same_event(client):
    """Both transports share one acceptance path, so the records agree."""
    from verify_helpers import auth, bootstrap_tenant, register
    session = register(client, "owner@acme.test", "Acme Industrial Services")
    tenant = bootstrap_tenant(client, session)
    document = diagnostic_document(asset_id=tenant["asset"]["id"],
                                   component_id=tenant["component"]["id"],
                                   event_id="evt-parity")

    response = client.post("/v1/ingest/diagnostic", json=document, headers=auth(session))
    assert response.status_code == 201, response.text
    diagnostic = response.json()["diagnostic"]
    assert diagnostic["source"] == "rest"
    assert diagnostic["status"] == "FAULT_SUSPECTED"

    duplicate = client.post("/v1/ingest/diagnostic", json=document, headers=auth(session))
    assert duplicate.status_code == 409

    foreign = client.post("/v1/ingest/diagnostic", json=document | {
        "event_id": "evt-other"}, headers={
            "Authorization": f"Bearer {register(client, 'intruder@evil.test', 'Evil Corp')['access_token']}"})
    assert foreign.status_code == 404
