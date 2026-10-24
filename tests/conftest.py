"""Shared fixtures for the AXON Verify test suite."""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("AXON_STORAGE_MODE", "memory")


@pytest.fixture(autouse=True)
def fast_passwords(monkeypatch):
    """Keep PBKDF2 at a test-friendly iteration count.

    Production default is 390k iterations; the algorithm and output format are
    identical, only the work factor is reduced so the suite stays fast.
    """
    monkeypatch.setenv("AXON_PBKDF2_ITERATIONS", "10000")


@pytest.fixture()
def client():
    from backend.main import create_app
    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture()
def owner(client):
    """A registered organisation owned by the caller."""
    from verify_helpers import register
    return register(client, "owner@acme.test", "Acme Industrial Services")
