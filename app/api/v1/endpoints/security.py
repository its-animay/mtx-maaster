import logging
import os
import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.security.api_keys import generate_api_key, hash_api_key, register_api_key, is_raw_key_valid
from app.security.rate_limit import RateLimiter
from app.core.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter()

default_limiter = RateLimiter(limit=60, window_seconds=60)
burst_limiter = RateLimiter(limit=10, window_seconds=60)


def admin_guard(
    x_admin_key: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    """
    Allow access if:
    - X-Admin-Key matches ADMIN_MASTER_KEY (constant-time compare), OR
    - X-API-Key is a registered API key.
    """

    settings = get_settings()
    if settings.admin_master_key and x_admin_key:
        if hmac.compare_digest(x_admin_key, settings.admin_master_key):
            return
    if x_api_key and is_raw_key_valid(x_api_key):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid or missing admin/API key")


@router.get("/public/ping")
def public_ping() -> dict:
    return {"status": "ok", "message": "public endpoint"}


@router.get("/secure/data", dependencies=[Depends(default_limiter)])
def secure_data() -> dict:
    return {"secret": "secured payload", "limit": "60/min"}


@router.get("/secure/burst", dependencies=[Depends(burst_limiter)])
def secure_burst() -> dict:
    return {"secret": "burst-limited payload", "limit": "10/min"}


@router.post("/admin/generate-key", dependencies=[Depends(admin_guard)])
def admin_generate_key(register: bool = True) -> dict:
    """
    Admin helper: generates a new API key and returns raw + hashed.
    Raw must be stored securely by the caller; hashed can be persisted server-side.
    """

    key, hashed = generate_api_key()
    if register:
        register_api_key(key)
    return {"api_key": key, "hashed": hashed, "registered": register}


def seed_demo_key_from_env() -> None:
    """Optional helper to register a demo key from env on startup."""

    settings = get_settings()
    demo_key = settings.demo_api_key or os.getenv("DEMO_API_KEY") or os.getenv("MQDB_DEMO_API_KEY")
    if not demo_key:
        logger.info("No DEMO_API_KEY provided; secure endpoints will reject requests until a key is registered.")
        return
    try:
        register_api_key(demo_key)
        logger.info("Registered demo API key from env (hashed only). Use provided raw key to call secured APIs.")
    except RuntimeError as exc:
        logger.warning("Failed to register DEMO_API_KEY: %s", exc)
