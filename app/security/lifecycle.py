from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from threading import RLock

from app.security.capabilities import UsagePolicy
from app.security.verification import CapabilityVerificationError, VerifiedCapability


class CapabilityLifecycleState(str, Enum):
    ACTIVE = "ACTIVE"
    USED = "USED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


class CapabilityLifecycleError(ValueError):
    """Base error for lifecycle and replay failures."""


class CapabilityReplayError(CapabilityLifecycleError):
    """Raised when a one-time capability is used again."""


class CapabilityExpiredError(CapabilityLifecycleError):
    """Raised when a capability is used after expiry."""


class CapabilityRevokedError(CapabilityLifecycleError):
    """Raised when a revoked capability is used."""


class CapabilityStateError(CapabilityLifecycleError):
    """Raised for invalid lifecycle transitions or untrusted inputs."""


class _LifecycleRecord:
    def __init__(self):
        self.state = CapabilityLifecycleState.ACTIVE


class CapabilityLifecycleStore:
    """Process-local lifecycle state for verified capabilities.

    This store prevents replay within this process. It does not provide
    cross-process or distributed replay protection.
    """

    def __init__(self):
        self._records: dict[str, _LifecycleRecord] = {}
        self._lock = RLock()

    @staticmethod
    def _require_verified(capability: VerifiedCapability) -> None:
        if not isinstance(capability, VerifiedCapability) or not capability.is_verified():
            raise CapabilityStateError("lifecycle requires a genuine VerifiedCapability")

    @staticmethod
    def _key(capability: VerifiedCapability) -> str:
        return f"{capability.claims.capability_id}:{capability.claims.nonce}"

    @staticmethod
    def _now(now: datetime | None) -> datetime:
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None or current.utcoffset() is None:
            raise CapabilityStateError("lifecycle time must be timezone-aware")
        return current.astimezone(timezone.utc)

    def _record_for(self, capability: VerifiedCapability) -> _LifecycleRecord:
        return self._records.setdefault(self._key(capability), _LifecycleRecord())

    def state(self, capability: VerifiedCapability, *, now: datetime | None = None) -> CapabilityLifecycleState:
        self._require_verified(capability)
        current = self._now(now)
        with self._lock:
            record = self._record_for(capability)
            if record.state == CapabilityLifecycleState.ACTIVE and current >= capability.claims.expires_at:
                record.state = CapabilityLifecycleState.EXPIRED
            return record.state

    def check_usable(self, capability: VerifiedCapability, *, now: datetime | None = None) -> VerifiedCapability:
        current_state = self.state(capability, now=now)
        if current_state == CapabilityLifecycleState.EXPIRED:
            raise CapabilityExpiredError("capability is expired")
        if current_state == CapabilityLifecycleState.REVOKED:
            raise CapabilityRevokedError("capability is revoked")
        if current_state == CapabilityLifecycleState.USED:
            raise CapabilityReplayError("one-time capability has already been used")
        return capability

    def verify_and_consume(
        self,
        capability: VerifiedCapability,
        *,
        now: datetime | None = None,
    ) -> VerifiedCapability:
        """Atomically check and consume a one-time capability."""
        self._require_verified(capability)
        current = self._now(now)
        with self._lock:
            record = self._record_for(capability)
            if record.state == CapabilityLifecycleState.ACTIVE and current >= capability.claims.expires_at:
                record.state = CapabilityLifecycleState.EXPIRED
            if record.state == CapabilityLifecycleState.EXPIRED:
                raise CapabilityExpiredError("capability is expired")
            if record.state == CapabilityLifecycleState.REVOKED:
                raise CapabilityRevokedError("capability is revoked")
            if record.state == CapabilityLifecycleState.USED:
                raise CapabilityReplayError("one-time capability has already been used")
            if capability.claims.usage_policy == UsagePolicy.ONE_TIME:
                record.state = CapabilityLifecycleState.USED
            return capability

    def revoke(self, capability: VerifiedCapability, *, now: datetime | None = None) -> None:
        self._require_verified(capability)
        current = self._now(now)
        with self._lock:
            record = self._record_for(capability)
            if record.state == CapabilityLifecycleState.ACTIVE and current >= capability.claims.expires_at:
                record.state = CapabilityLifecycleState.EXPIRED
            if record.state == CapabilityLifecycleState.USED:
                raise CapabilityStateError("used capability cannot be revoked")
            if record.state == CapabilityLifecycleState.EXPIRED:
                raise CapabilityStateError("expired capability cannot be revoked")
            if record.state == CapabilityLifecycleState.REVOKED:
                raise CapabilityStateError("capability is already revoked")
            record.state = CapabilityLifecycleState.REVOKED


__all__ = [
    "CapabilityExpiredError",
    "CapabilityLifecycleError",
    "CapabilityLifecycleState",
    "CapabilityLifecycleStore",
    "CapabilityReplayError",
    "CapabilityRevokedError",
    "CapabilityStateError",
]
