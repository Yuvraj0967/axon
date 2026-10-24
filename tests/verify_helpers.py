"""Helpers shared by the AXON Verify API tests."""
from __future__ import annotations

from fastapi.testclient import TestClient

PASSWORD = "correct-horse-battery"


def register(client: TestClient, email: str, org_name: str,
             password: str = PASSWORD) -> dict:
    response = client.post("/v1/auth/register", json={
        "email": email, "password": password, "name": email.split("@")[0].title(),
        "org_name": org_name})
    assert response.status_code == 201, response.text
    return response.json()


def auth(session: dict) -> dict:
    return {"Authorization": f"Bearer {session['access_token']}"}


def bootstrap_tenant(client: TestClient, session: dict) -> dict:
    """Create the customer, site, asset and component a workflow needs."""
    headers = auth(session)
    customer = client.post("/v1/customers", json={"name": "Northwind Mills"},
                           headers=headers).json()
    site = client.post("/v1/sites", json={"customer_id": customer["id"], "name": "Plant 1"},
                       headers=headers).json()
    asset = client.post("/v1/assets", json={
        "site_id": site["id"], "customer_id": customer["id"], "name": "Pump P-101",
        "manufacturer": "Sulzer", "model": "CA20", "serial": "SN-4471"},
        headers=headers).json()
    assert "components" in asset and asset["components"], asset
    return {"customer": customer, "site": site, "asset": asset,
            "component": asset["components"][0], "headers": headers}


def invite(client: TestClient, session: dict, email: str, role: str) -> dict:
    return client.post("/v1/team", json={
        "email": email, "name": email.split("@")[0].title(), "role": role,
        "password": PASSWORD}, headers=auth(session)).json()


def login(client: TestClient, email: str) -> dict:
    return client.post("/v1/auth/login",
                       json={"email": email, "password": PASSWORD}).json()


def start_work_order(client: TestClient, tenant: dict, headers: dict | None = None,
                     title: str = "Replace drive-end bearing") -> dict:
    order = client.post("/v1/work-orders", json={
        "asset_id": tenant["asset"]["id"], "component_id": tenant["component"]["id"],
        "title": title}, headers=headers or tenant["headers"])
    assert order.status_code == 201, order.text
    return order.json()


def start_repair(client: TestClient, work_order_id: str, headers: dict) -> dict:
    repair = client.post(f"/v1/work-orders/{work_order_id}/repairs", json={},
                         headers=headers)
    assert repair.status_code == 201, repair.text
    return repair.json()


def capture_replay(client: TestClient, repair_id: str, headers: dict, phase: str,
                   recording_id: str, window_index: int = 0) -> dict:
    response = client.post(f"/v1/repairs/{repair_id}/capture", json={
        "phase": phase, "source": "replay", "recording_id": recording_id,
        "window_index": window_index}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()
