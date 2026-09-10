from __future__ import annotations

import hashlib
import hmac

from app.security.capabilities import CapabilityClaims
from app.security.canonical import canonicalize_claims

_MIN_KEY_BYTES = 32


def _validate_key(secret_key: bytes) -> bytes:
    if not isinstance(secret_key, bytes):
        raise TypeError("secret_key must be bytes")
    if len(secret_key) < _MIN_KEY_BYTES:
        raise ValueError("secret_key must contain at least 32 bytes")
    return secret_key


def compute_mac(claims: CapabilityClaims, secret_key: bytes) -> str:
    """Return the hex HMAC-SHA256 for the complete canonical claims payload."""
    key = _validate_key(secret_key)
    return hmac.new(key, canonicalize_claims(claims), hashlib.sha256).hexdigest()


def verify_mac(claims: CapabilityClaims, secret_key: bytes, mac: str) -> bool:
    """Compare a supplied MAC in constant time without authorization decisions."""
    if not isinstance(mac, str):
        return False
    try:
        expected = compute_mac(claims, secret_key)
    except (TypeError, ValueError):
        return False
    return hmac.compare_digest(expected, mac)


__all__ = ["compute_mac", "verify_mac"]
