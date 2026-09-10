from __future__ import annotations

import os
from pathlib import Path

from app.security.crypto import _validate_key

_DEFAULT_KEY_DIR = Path.home() / ".local" / "permission_aware_automation"
_DEFAULT_KEY_FILE = _DEFAULT_KEY_DIR / "capability_hmac.key"
_ENV_KEY = "CAPABILITY_HMAC_KEY"


class CapabilityKeyProvider:
    """M5-owned source of the capability signing secret."""

    def __init__(self, *, secret_key: bytes | None = None):
        if secret_key is not None:
            self._secret_key = _validate_key(secret_key)
            self._owned = False
        else:
            self._secret_key = _load_or_create_persistent_key()
            self._owned = True

    def get_signing_key(self) -> bytes:
        return self._secret_key

    @classmethod
    def for_testing(cls, secret_key: bytes) -> "CapabilityKeyProvider":
        """Create a provider with a deterministic key for tests only."""
        return cls(secret_key=secret_key)


def _load_or_create_persistent_key() -> bytes:
    env_value = os.environ.get(_ENV_KEY)
    if env_value:
        return _validate_key(env_value.encode("utf-8"))

    if _DEFAULT_KEY_FILE.is_file():
        return _validate_key(_DEFAULT_KEY_FILE.read_bytes())

    _DEFAULT_KEY_DIR.mkdir(parents=True, exist_ok=True)
    key = os.urandom(32)
    _DEFAULT_KEY_FILE.write_bytes(key)
    return key


__all__ = ["CapabilityKeyProvider"]
