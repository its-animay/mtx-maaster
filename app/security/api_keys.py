import hashlib
import hmac
import logging
import os
import secrets
import threading
from typing import Optional, Set

from fastapi import Depends, Header, HTTPException, status

logger = logging.getLogger(__name__)

_salt_lock = threading.Lock()
_salt: Optional[str] = None
_api_key_store: Set[str] = set()


def _get_salt() -> str:
    """Fetch and cache the API key salt from environment."""

    global _salt
    if _salt is None:
        with _salt_lock:
            if _salt is None:
                try:
                    from app.core.config import get_settings

                    env_salt = get_settings().api_key_salt
                except Exception:
                    env_salt = os.getenv("API_KEY_SALT") or os.getenv("MQDB_API_KEY_SALT")
                if not env_salt:
                    raise RuntimeError("API_KEY_SALT environment variable is required for API key verification")
                _salt = env_salt
    return _salt


def hash_api_key(raw_key: str) -> str:
    """Return salted sha256 hash for storage/verification."""

    salt = _get_salt()
    return hashlib.sha256(f"{raw_key}{salt}".encode("utf-8")).hexdigest()


def add_hashed_key(hashed_key: str) -> None:
    """Register a pre-hashed key (hash only, not raw)."""

    _api_key_store.add(hashed_key)


def is_raw_key_valid(raw_key: str) -> bool:
    """Check if a raw key matches any stored hash."""

    hashed = hash_api_key(raw_key)
    return any(hmac.compare_digest(hashed, candidate) for candidate in _api_key_store)


def register_api_key(raw_key: str) -> str:
    """Hash and register a raw key; raw is NOT persisted."""

    hashed = hash_api_key(raw_key)
    add_hashed_key(hashed)
    return hashed


def generate_api_key() -> tuple[str, str]:
    """Generate a new API key (raw + hashed). Caller stores raw securely."""

    key = secrets.token_urlsafe(32)
    hashed = hash_api_key(key)
    logger.info("Generated new API key (hashed stored/returned; raw should be kept secret).")
    return key, hashed


def verify_api_key(x_api_key: Optional[str] = Header(default=None)) -> str:
    """Dependency to validate incoming API key header and return hashed key."""

    if not x_api_key:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid or missing API Key")

    hashed = hash_api_key(x_api_key)
    valid = any(hmac.compare_digest(hashed, candidate) for candidate in _api_key_store)
    if not valid:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid or missing API Key")
    return hashed


def require_api_key(hashed_key: str = Depends(verify_api_key)) -> str:
    """Shortcut dependency when only API key verification is needed."""

    return hashed_key
