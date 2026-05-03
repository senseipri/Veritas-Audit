import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("VERITAS_API_KEYS", "company-a:key-a,company-b:key-b")
    monkeypatch.setenv("VERITAS_ADMIN_KEY", "admin-key")
    monkeypatch.setenv("VERITAS_RATE_LIMIT_PER_MINUTE", "2")


def _client(monkeypatch):
    # Import inside to pick up env vars
    import src.api as api

    # Ensure rate limiter state doesn't leak across tests
    api._RATE_LIMIT_BUCKETS.clear()

    return TestClient(api.app)


def test_missing_api_key_is_401(monkeypatch):
    c = _client(monkeypatch)
    r = c.get("/v1/tenants")
    assert r.status_code == 401


def test_tenant_key_can_only_access_own_tenant(monkeypatch):
    c = _client(monkeypatch)
    # company-a key
    r1 = c.get("/v1/tenants", headers={"x-api-key": "key-a"})
    assert r1.status_code == 200
    assert r1.json()["tenants"] == ["company-a"]

    # cannot access company-b logs
    r2 = c.get("/v1/tenants/company-b/logs", headers={"x-api-key": "key-a"})
    assert r2.status_code == 403


def test_admin_key_lists_all_tenants(monkeypatch, tmp_path):
    # Create a couple tenant folders so listing has something to show
    repo_root = os.path.dirname(os.path.dirname(__file__))
    tenants_root = os.path.join(repo_root, "tenants")
    os.makedirs(os.path.join(tenants_root, "company-a"), exist_ok=True)
    os.makedirs(os.path.join(tenants_root, "company-b"), exist_ok=True)

    c = _client(monkeypatch)
    r = c.get("/v1/tenants", headers={"x-api-key": "admin-key"})
    assert r.status_code == 200
    assert "company-a" in r.json()["tenants"]
    assert "company-b" in r.json()["tenants"]


def test_rate_limit(monkeypatch):
    c = _client(monkeypatch)
    headers = {"x-api-key": "key-a"}
    # 2 allowed / minute
    assert c.get("/v1/tenants", headers=headers).status_code == 200
    assert c.get("/v1/tenants", headers=headers).status_code == 200
    third = c.get("/v1/tenants", headers=headers)
    assert third.status_code == 429

