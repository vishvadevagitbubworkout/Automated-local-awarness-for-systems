from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping

from app.security.capabilities import CapabilityClaims


def _canonical_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        normalized = value.astimezone(timezone.utc)
        return normalized.isoformat(timespec="microseconds").replace("+00:00", "Z")
    if isinstance(value, Mapping):
        return {str(key): _canonical_value(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise TypeError(f"Unsupported canonical value type: {type(value).__name__}")


def claims_payload(claims: CapabilityClaims) -> dict[str, Any]:
    if not isinstance(claims, CapabilityClaims):
        raise TypeError("claims_payload expects CapabilityClaims")

    return {
        "agent": claims.agent,
        "capability_id": claims.capability_id,
        "constraints": _canonical_value(claims.constraints),
        "expires_at": _canonical_value(claims.expires_at),
        "issued_at": _canonical_value(claims.issued_at),
        "nonce": claims.nonce,
        "operation": claims.operation,
        "resource": claims.resource,
        "scope": {
            "kind": claims.scope.kind.value,
            "resource_id": claims.scope.resource_id,
            "resource_type": claims.scope.resource_type.value,
            "selector": claims.scope.selector,
        },
        "step_id": claims.step_id,
        "task_id": claims.task_id,
        "usage_policy": claims.usage_policy.value,
    }


def canonicalize_claims(claims: CapabilityClaims) -> bytes:
    """Serialize all immutable capability claims into deterministic UTF-8 JSON bytes.

    Contract: the complete fixed field set from ``claims_payload`` is included;
    JSON objects use lexicographically sorted keys, lists preserve their order,
    enums use their string values, datetimes use UTC ISO-8601 with six fractional
    digits and a trailing ``Z``, nulls are retained, and UTF-8 is used with
    compact separators and no ASCII escaping. No lifecycle state or secret key
    is part of the payload.
    """
    payload = claims_payload(claims)
    serialized = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return serialized.encode("utf-8")


__all__ = ["canonicalize_claims", "claims_payload"]
