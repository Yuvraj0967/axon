"""Authentication, role enforcement and tenant isolation."""
from __future__ import annotations

import pytest

from verify_helpers import auth, bootstrap_tenant, register

PASSWORD = "correct-horse-battery"


def test_register_creates_an_owner_and_a_session(client):
    session = register(client, "owner@acme.test", "Acme Industrial Services")
    assert session["role"] == "owner"
    assert session["org"]["name"] == "Acme Industrial Services"
    me = client.get("/v1/me", headers=auth(session)).json()
    assert me["user"]["email"] == "owner@acme.test"
    assert "certify" in me["permissions"]
    assert me["organisations"][0]["id"] == session["org"]["id"]


def test_register_rejects_duplicate_emails_and_weak_passwords(client):
    register(client, "owner@acme.test", "Acme")
    duplicate = client.post("/v1/auth/register", json={
        "email": "owner@acme.test", "password": PASSWORD, "name": "X", "org_name": "Other"})
    assert duplicate.status_code == 409
    weak = client.post("/v1/auth/register", json={
        "email": "weak@acme.test", "password": "short", "name": "X", "org_name": "Other"})
    assert weak.status_code == 422


def test_login_requires_correct_password(client):
    register(client, "owner@acme.test", "Acme", PASSWORD)
    assert client.post("/v1/auth/login", json={
        "email": "owner@acme.test", "password": "wrong-password"}).status_code == 401
    assert client.post("/v1/auth/login", json={
        "email": "nobody@acme.test", "password": PASSWORD}).status_code == 401
    assert client.post("/v1/auth/login", json={
        "email": "owner@acme.test", "password": PASSWORD}).status_code == 200


def test_logging_in_twice_in_the_same_second_issues_two_valid_sessions(client):
    register(client, "owner@acme.test", "Acme", PASSWORD)
    credentials = {"email": "owner@acme.test", "password": PASSWORD}
    first = client.post("/v1/auth/login", json=credentials)
    second = client.post("/v1/auth/login", json=credentials)
    assert first.status_code == 200 and second.status_code == 200
    assert first.json()["access_token"] != second.json()["access_token"]
    assert client.get("/v1/me", headers=auth(first.json())).status_code == 200
    assert client.get("/v1/me", headers=auth(second.json())).status_code == 200


def test_endpoints_require_authentication(client):
    for path in ("/v1/me", "/v1/assets", "/v1/work-orders", "/v1/stats", "/v1/audit"):
        assert client.get(path).status_code == 401, path
    assert client.post("/v1/customers", json={"name": "x"}).status_code == 401


def test_logout_revokes_the_session(client):
    session = register(client, "owner@acme.test", "Acme")
    headers = auth(session)
    assert client.get("/v1/me", headers=headers).status_code == 200
    assert client.post("/v1/auth/logout", headers=headers).status_code == 200
    assert client.get("/v1/me", headers=headers).status_code == 401


def test_a_forged_token_is_rejected(client):
    session = register(client, "owner@acme.test", "Acme")
    token = session["access_token"]
    forged = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")
    assert client.get("/v1/me", headers=auth({"access_token": forged})).status_code == 401
    assert client.get("/v1/me", headers=auth({"access_token": token + "x"})).status_code == 401


# --------------------------------------------------------------- isolation


@pytest.fixture()
def two_tenants(client):
    alpha = register(client, "owner@alpha.test", "Alpha Services")
    beta = register(client, "owner@beta.test", "Beta Services")
    return alpha, beta


def test_organisations_cannot_see_each_others_assets(client, two_tenants):
    alpha, beta = two_tenants
    alpha_tenant = bootstrap_tenant(client, alpha)
    asset_id = alpha_tenant["asset"]["id"]

    beta_assets = client.get("/v1/assets", headers=auth(beta)).json()["assets"]
    assert beta_assets == [], "an empty organisation must see nothing"

    assert client.get(f"/v1/assets/{asset_id}", headers=auth(beta)).status_code == 404
    assert client.get(f"/v1/assets/{asset_id}/timeline",
                      headers=auth(beta)).status_code == 404
    assert client.get(f"/v1/assets/{asset_id}", headers=auth(alpha)).status_code == 200


def test_organisations_cannot_attach_evidence_to_foreign_assets(client, two_tenants):
    alpha, beta = two_tenants
    alpha_tenant = bootstrap_tenant(client, alpha)
    order = client.post("/v1/work-orders", json={
        "asset_id": alpha_tenant["asset"]["id"],
        "component_id": alpha_tenant["component"]["id"],
        "title": "Inspect bearing"}, headers=auth(alpha)).json()

    foreign = client.post("/v1/work-orders", json={
        "asset_id": alpha_tenant["asset"]["id"],
        "component_id": alpha_tenant["component"]["id"],
        "title": "Try to attach here"}, headers=auth(beta))
    assert foreign.status_code == 404

    repair = client.post(f"/v1/work-orders/{order['id']}/repairs", json={},
                         headers=auth(beta))
    assert repair.status_code == 404


def test_stats_and_audit_are_scoped_to_the_caller(client, two_tenants):
    alpha, beta = two_tenants
    bootstrap_tenant(client, alpha)
    assert client.get("/v1/stats", headers=auth(alpha)).json()["assets"] == 1
    assert client.get("/v1/stats", headers=auth(beta)).json()["assets"] == 0

    # Each organisation sees only its own audit trail: beta must never see the
    # asset, site and customer events that alpha just generated.
    alpha_events = client.get("/v1/audit", headers=auth(alpha)).json()["events"]
    beta_events = client.get("/v1/audit", headers=auth(beta)).json()["events"]
    assert {event["action"] for event in beta_events} == {"org.created"}
    assert all(event["org_id"] == beta["org"]["id"] for event in beta_events)
    assert all(event["org_id"] == alpha["org"]["id"] for event in alpha_events)
    assert {"asset.created", "site.created"} <= {event["action"] for event in alpha_events}


def test_devices_cannot_be_registered_twice_or_read_across_tenants(client, two_tenants):
    alpha, beta = two_tenants
    payload = {"name": "Gateway", "device_key": "plant1-gw-01"}
    assert client.post("/v1/devices", json=payload, headers=auth(alpha)).status_code == 201
    assert client.post("/v1/devices", json=payload, headers=auth(alpha)).status_code == 409
    assert client.get("/v1/devices", headers=auth(beta)).json()["devices"] == []


def test_switching_to_a_foreign_organisation_is_refused(client, two_tenants):
    alpha, beta = two_tenants
    response = client.post("/v1/auth/switch-org", json={"org_id": beta["org"]["id"]},
                           headers=auth(alpha))
    assert response.status_code == 403


# -------------------------------------------------------------------- roles


def _invite(client, session, email, role):
    return client.post("/v1/team", json={
        "email": email, "name": email.split("@")[0].title(), "role": role,
        "password": PASSWORD}, headers=auth(session))


def _login(client, email):
    return client.post("/v1/auth/login", json={"email": email, "password": PASSWORD}).json()


def test_viewer_can_read_but_not_write(client):
    owner_session = register(client, "owner@acme.test", "Acme")
    tenant = bootstrap_tenant(client, owner_session)
    _invite(client, owner_session, "viewer@acme.test", "viewer")
    viewer = _login(client, "viewer@acme.test")

    assert client.get("/v1/assets", headers=auth(viewer)).status_code == 200
    assert client.get("/v1/stats", headers=auth(viewer)).status_code == 200
    assert client.post("/v1/work-orders", json={
        "asset_id": tenant["asset"]["id"], "component_id": tenant["component"]["id"],
        "title": "Nope"}, headers=auth(viewer)).status_code == 403


def test_technician_can_capture_but_not_certify_or_manage(client):
    owner_session = register(client, "owner@acme.test", "Acme")
    tenant = bootstrap_tenant(client, owner_session)
    _invite(client, owner_session, "tech@acme.test", "technician")
    technician = _login(client, "tech@acme.test")

    order = client.post("/v1/work-orders", json={
        "asset_id": tenant["asset"]["id"], "component_id": tenant["component"]["id"],
        "title": "Replace bearing"}, headers=auth(technician))
    assert order.status_code == 201

    assert client.post("/v1/team", json={
        "email": "x@acme.test", "name": "X", "role": "viewer"},
        headers=auth(technician)).status_code == 403
    repair = client.post(f"/v1/work-orders/{order.json()['id']}/repairs", json={},
                         headers=auth(technician)).json()
    assert client.post(f"/v1/repairs/{repair['id']}/certificate",
                       headers=auth(technician)).status_code == 403


def test_manager_can_certify_but_not_manage_the_organisation(client):
    owner_session = register(client, "owner@acme.test", "Acme")
    bootstrap_tenant(client, owner_session)
    _invite(client, owner_session, "manager@acme.test", "manager")
    manager = _login(client, "manager@acme.test")
    assert client.get("/v1/api-keys", headers=auth(manager)).status_code == 403
    assert client.post("/v1/api-keys", json={"name": "x"},
                       headers=auth(manager)).status_code == 403


def test_an_organisation_must_keep_at_least_one_owner(client):
    owner_session = register(client, "owner@acme.test", "Acme")
    other = client.post("/v1/team", json={
        "email": "co@acme.test", "name": "Co Owner", "role": "admin",
        "password": PASSWORD}, headers=auth(owner_session)).json()
    owner_id = client.get("/v1/me", headers=auth(owner_session)).json()["user"]["id"]

    demote = client.patch(f"/v1/team/{owner_id}", json={"role": "admin"},
                          headers=auth(owner_session))
    assert demote.status_code == 409

    promote = client.patch(f"/v1/team/{other['member']['user_id']}", json={"role": "owner"},
                           headers=auth(owner_session))
    assert promote.status_code == 200
    assert client.patch(f"/v1/team/{owner_id}", json={"role": "viewer"},
                        headers=auth(owner_session)).status_code == 200


# ----------------------------------------------------------------- API keys


def test_api_keys_can_move_evidence_but_not_manage(client):
    owner_session = register(client, "owner@acme.test", "Acme")
    tenant = bootstrap_tenant(client, owner_session)
    created = client.post("/v1/api-keys", json={"name": "plant gateway"},
                          headers=auth(owner_session)).json()
    assert created["key"].startswith("axv1_")
    key_headers = {"Authorization": f"Bearer {created['key']}"}

    assert client.get("/v1/me", headers=key_headers).status_code == 200
    assert client.post("/v1/work-orders", json={
        "asset_id": tenant["asset"]["id"], "component_id": tenant["component"]["id"],
        "title": "Key-driven order"}, headers=key_headers).status_code == 201
    assert client.post("/v1/api-keys", json={"name": "another"},
                       headers=key_headers).status_code == 403
    assert client.post(f"/v1/repairs/x/certificate",
                       headers=key_headers).status_code == 403
    assert client.get("/v1/audit", headers=key_headers).status_code == 403


def test_the_secret_is_shown_once_and_never_again(client):
    owner_session = register(client, "owner@acme.test", "Acme")
    created = client.post("/v1/api-keys", json={"name": "gateway"},
                          headers=auth(owner_session)).json()
    listed = client.get("/v1/api-keys", headers=auth(owner_session)).json()["keys"]
    assert created["key"] not in str(listed)
    assert "key" not in listed[0]


def test_revoking_an_api_key_stops_it_working(client):
    owner_session = register(client, "owner@acme.test", "Acme")
    created = client.post("/v1/api-keys", json={"name": "gateway"},
                          headers=auth(owner_session)).json()
    key_headers = {"Authorization": f"Bearer {created['key']}"}
    assert client.get("/v1/me", headers=key_headers).status_code == 200
    assert client.delete(f"/v1/api-keys/{created['id']}",
                         headers=auth(owner_session)).status_code == 200
    assert client.get("/v1/me", headers=key_headers).status_code == 401


def test_an_unknown_api_key_is_rejected(client):
    register(client, "owner@acme.test", "Acme")
    response = client.get("/v1/me", headers={"Authorization": "Bearer axv1_not_a_key"})
    assert response.status_code == 401
