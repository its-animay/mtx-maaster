import os
import time
from typing import Generator

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.v1.endpoints.security import admin_guard
from app.core.config import get_settings
from app.security.api_keys import (
    _api_key_store,
    _salt,
    generate_api_key,
    register_api_key,
    require_api_key,
)
from app.security.rate_limit import RateLimiter


@pytest.fixture(autouse=True)
def reset_security_env(monkeypatch) -> Generator[None, None, None]:
    """Ensure salt/admin key and stores reset for each test."""

    monkeypatch.setenv("API_KEY_SALT", "test-salt")
    monkeypatch.setenv("ADMIN_MASTER_KEY", "admin-secret")
    # Clear cached settings so env is re-read
    get_settings.cache_clear()  # type: ignore[attr-defined]
    # Reset security module state
    _api_key_store.clear()
    # reset salt cache
    import app.security.api_keys as api_keys

    api_keys._salt = None  # type: ignore[attr-defined]
    yield
    get_settings.cache_clear()  # type: ignore[attr-defined]
    _api_key_store.clear()
    api_keys._salt = None  # type: ignore[attr-defined]


def test_api_key_verification_success_and_missing() -> None:
    app = FastAPI()
    app.get("/protected", dependencies=[Depends(require_api_key)])(lambda: {"ok": True})

    # Register a key and build client
    raw_key, _ = generate_api_key()
    register_api_key(raw_key)
    client = TestClient(app)

    # Success
    resp_ok = client.get("/protected", headers={"X-API-Key": raw_key})
    assert resp_ok.status_code == 200
    assert resp_ok.json() == {"ok": True}

    # Missing/invalid
    resp_forbidden = client.get("/protected")
    assert resp_forbidden.status_code == 403


def test_rate_limiter_enforces_limits() -> None:
    app = FastAPI()
    limiter = RateLimiter(limit=2, window_seconds=60)
    app.get("/limited", dependencies=[Depends(limiter)])(lambda: {"ok": True})

    raw_key, _ = generate_api_key()
    register_api_key(raw_key)
    client = TestClient(app)

    assert client.get("/limited", headers={"X-API-Key": raw_key}).status_code == 200
    assert client.get("/limited", headers={"X-API-Key": raw_key}).status_code == 200
    resp = client.get("/limited", headers={"X-API-Key": raw_key})
    assert resp.status_code == 429


def test_admin_guard_allows_master_key() -> None:
    app = FastAPI()

    @app.get("/admin-only", dependencies=[Depends(admin_guard)])
    def admin_only():
        return {"admin": True}

    client = TestClient(app)

    # With master key
    resp_ok = client.get("/admin-only", headers={"X-Admin-Key": "admin-secret"})
    assert resp_ok.status_code == 200
    assert resp_ok.json() == {"admin": True}

    # Without master/API key
    resp_forbidden = client.get("/admin-only")
    assert resp_forbidden.status_code == 403
