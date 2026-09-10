from datetime import datetime, timedelta, timezone
import json

import pytest

from app.capabilities.templates import ResourceType
from app.permissions.policies import PermissionScope, PermissionScopeKind
from app.security.capabilities import AuthenticatedCapability, CapabilityClaims, UsagePolicy
from app.security.crypto import compute_mac
from app.security.key_provider import CapabilityKeyProvider
from app.security.minting import CapabilityMinter
from app.security.verification import (
    CapabilityVerificationError,
    CapabilityVerifier,
    VerifiedCapability,
)
from tests.test_capability_minting import KEY, allowed, plan, scope


def provider(key=KEY):
    return CapabilityKeyProvider.for_testing(key)


def minted():
    task = plan()
    capability = CapabilityMinter(key_provider=provider()).mint(
        allowed(task), task, task.steps[0]
    )
    return capability, task


def test_genuine_capability_verifies():
    capability, task = minted()

    verified = CapabilityVerifier(key_provider=provider()).verify(
        capability,
        expected_task_id=task.task_id,
        expected_step_id=task.steps[0].step_id,
        expected_agent="file_manager",
        expected_operation="READ",
        expected_resource="report.pdf",
        expected_scope=scope("report.pdf"),
    )

    assert isinstance(verified, VerifiedCapability)
    assert verified.is_verified()
    assert verified.claims.task_id == "task_001"


def test_serialized_capability_verifies():
    capability, _ = minted()
    serialized = capability.model_dump_json()

    verified = CapabilityVerifier(key_provider=provider()).verify(serialized)

    assert verified.is_verified()
    assert verified.mac == capability.mac


@pytest.mark.parametrize(
    "field, value",
    [
        ("task_id", "task_999"),
        ("step_id", "step_999"),
        ("agent", "browser_agent"),
        ("operation", "DELETE"),
        ("resource", "secret.pdf"),
        ("nonce", "fedcba9876543210"),
    ],
)
def test_claim_tampering_with_old_mac_is_rejected(field, value):
    capability, _ = minted()
    payload = capability.model_dump(mode="json")
    payload["claims"][field] = value

    with pytest.raises(CapabilityVerificationError, match="MAC"):
        CapabilityVerifier(key_provider=provider()).verify(payload)


def test_constraint_and_expiry_tampering_with_old_mac_is_rejected():
    capability, _ = minted()
    payload = capability.model_dump(mode="json")
    payload["claims"]["constraints"]["mode"] = "delete"

    with pytest.raises(CapabilityVerificationError, match="MAC"):
        CapabilityVerifier(key_provider=provider()).verify(payload)

    payload = capability.model_dump(mode="json")
    payload["claims"]["expires_at"] = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    with pytest.raises(CapabilityVerificationError, match="MAC"):
        CapabilityVerifier(key_provider=provider()).verify(payload)


def test_mac_tampering_wrong_key_and_malformed_mac_are_rejected():
    capability, _ = minted()
    verifier = CapabilityVerifier(key_provider=provider())

    for mac in ["0" * 64, capability.mac[:-1], "not-a-mac", ""]:
        payload = capability.model_dump(mode="json")
        payload["mac"] = mac
        with pytest.raises(CapabilityVerificationError):
            verifier.verify(payload)

    with pytest.raises(CapabilityVerificationError, match="MAC"):
        CapabilityVerifier(key_provider=provider(b"a" * 32)).verify(capability)


def test_expired_capability_is_rejected():
    now = datetime.now(timezone.utc)
    claims = CapabilityClaims(
        capability_id="file.read",
        task_id="task_001",
        step_id="step_001",
        agent="file_manager",
        operation="READ",
        resource="report.pdf",
        scope=scope("report.pdf"),
        constraints={"mode": "read"},
        issued_at=now - timedelta(minutes=10),
        expires_at=now - timedelta(minutes=1),
        nonce="0123456789abcdef",
        usage_policy=UsagePolicy.ONE_TIME,
    )
    capability = AuthenticatedCapability(claims=claims, mac=compute_mac(claims, KEY))

    with pytest.raises(CapabilityVerificationError, match="expired"):
        CapabilityVerifier(key_provider=provider()).verify(capability, now=now)


def test_context_substitution_is_rejected_after_mac_verification():
    capability, _ = minted()
    verifier = CapabilityVerifier(key_provider=provider())

    contexts = [
        {"expected_task_id": "task_999"},
        {"expected_step_id": "step_999"},
        {"expected_agent": "browser_agent"},
        {"expected_operation": "DELETE"},
        {"expected_resource": "secret.pdf"},
        {"expected_scope": scope("secret.pdf")},
    ]
    for context in contexts:
        with pytest.raises(CapabilityVerificationError, match="mismatch"):
            verifier.verify(capability, **context)


def test_malformed_capability_is_rejected():
    with pytest.raises(CapabilityVerificationError, match="malformed"):
        CapabilityVerifier(key_provider=provider()).verify({"claims": {}, "mac": ""})
    with pytest.raises(CapabilityVerificationError, match="malformed"):
        CapabilityVerifier(key_provider=provider()).verify("not-json")


def test_naive_verification_time_is_rejected():
    capability, _ = minted()

    with pytest.raises(CapabilityVerificationError, match="timezone-aware"):
        CapabilityVerifier(key_provider=provider()).verify(capability, now=datetime.now())


def test_verified_capability_is_immutable_and_not_retaggable():
    capability, _ = minted()
    verified = CapabilityVerifier(key_provider=provider()).verify(capability)

    with pytest.raises(Exception):
        verified.claims = capability.claims
    with pytest.raises(TypeError, match="retagged"):
        verified.model_copy(update={"claims": verified.claims})


def test_verification_does_not_add_replay_or_execution_behavior():
    capability, _ = minted()
    verified = CapabilityVerifier(key_provider=provider()).verify(capability)

    assert not hasattr(verified, "consume")
    assert not hasattr(verified, "state")
    assert not hasattr(verified, "execute")
