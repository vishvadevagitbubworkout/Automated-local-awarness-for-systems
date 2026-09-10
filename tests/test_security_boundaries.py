"""Security-property regression tests for M2/M4/M5 trust boundaries."""

import json

import pytest

from app.capabilities.templates import ResourceType
from app.intent.schemas import IntentCheckResult, ValidatedIntentResult
from app.intent.validator import IntentValidator
from app.permissions.authorization import AuthorizationResult, TaskAuthorizationManager
from app.permissions.policies import PermissionDecision, PermissionScope, PermissionScopeKind
from app.planner.schemas import PlanStep, TaskPlan
from app.security.capabilities import AuthenticatedCapability
from app.security.crypto import verify_mac
from app.security.key_provider import CapabilityKeyProvider
from app.security.minting import CapabilityMinter, CapabilityMintingError, CapabilityMintingPolicy
from app.security.lifecycle import CapabilityLifecycleStore
from app.security.verification import CapabilityVerifier
from tests.support import FakeOllamaClient, validated_intent_for_plan

KEY = b"0123456789abcdef0123456789abcdef0123456789abcdef0123456789ab"


def _scope(resource="report.pdf"):
    return PermissionScope(
        resource_type=ResourceType.FILE,
        kind=PermissionScopeKind.TASK,
        selector="current_task.resource",
        resource_id=resource,
    )


def _plan(resource="report.pdf", task_id="task_001"):
    return TaskPlan(
        task_id=task_id,
        original_request="Read report.pdf",
        steps=[
            PlanStep(
                step_id="step_001",
                agent="file_manager",
                operation="READ",
                resource=resource,
                parameters={"mode": "read"},
                template="FILE_READ",
                intent="READ",
            )
        ],
    )


def _minter():
    return CapabilityMinter(key_provider=CapabilityKeyProvider.for_testing(KEY))


def _genuine_authorization(task=None):
    task = task or _plan()
    return TaskAuthorizationManager().authorize_step(
        task,
        validated_intent_for_plan(task),
        "step_001",
        scope=_scope(task.steps[0].resource),
    )


# --- M5-001: Authorization forgery ---


def test_genuine_m4_authorization_mints_capability():
    task = _plan()
    authorization = _genuine_authorization(task)
    capability = _minter().mint(authorization, task, task.steps[0])

    assert authorization.decision == PermissionDecision.ALLOW
    assert verify_mac(capability.claims, KEY, capability.mac)


def test_direct_authorization_construction_cannot_mint():
    task = _plan()
    forged = AuthorizationResult(
        task_id=task.task_id,
        step_id="step_001",
        capability_id="file.read",
        decision=PermissionDecision.ALLOW,
        scope=_scope(),
        reason="forged",
    )

    assert not forged.is_integrity_valid()
    with pytest.raises(CapabilityMintingError, match="integrity"):
        _minter().mint(forged, task, task.steps[0])


def test_deserialized_authorization_cannot_mint():
    task = _plan()
    genuine = _genuine_authorization(task)
    payload = genuine.model_dump(mode="json")
    restored = AuthorizationResult.model_validate(payload)

    assert not restored.is_integrity_valid()
    with pytest.raises(CapabilityMintingError, match="integrity"):
        _minter().mint(restored, task, task.steps[0])


def test_model_copy_cannot_retag_authorization_into_genuine_allow():
    task = _plan()
    deny = TaskAuthorizationManager().authorize_step(
        task,
        validated_intent_for_plan(task),
        "step_001",
        scope=_scope("secret.pdf"),
    )
    assert deny.decision == PermissionDecision.DENY

    with pytest.raises(TypeError, match="retagged"):
        deny.model_copy(update={"decision": PermissionDecision.ALLOW, "capability_id": "file.read"})


def test_authorization_result_has_no_public_issuance_classmethod():
    assert not hasattr(AuthorizationResult, "_from_manager")


# --- M5-004: M2 validation forgery ---


def test_genuine_m2_result_is_accepted_by_m4():
    task = _plan()
    result = validated_intent_for_plan(task)

    assert result.is_m2_validated()
    authorization = TaskAuthorizationManager().authorize_step(
        task, result, "step_001", scope=_scope()
    )
    assert authorization.decision == PermissionDecision.ALLOW


def test_forged_validated_intent_result_is_rejected_by_m4():
    task = _plan()
    forged = ValidatedIntentResult(
        task_id=task.task_id,
        consistent=True,
        reason="forged",
        mismatched_steps=[],
    )

    assert not forged.is_m2_validated()
    authorization = TaskAuthorizationManager().authorize_step(
        task, forged, "step_001", scope=_scope()
    )
    assert authorization.decision == PermissionDecision.DENY


def test_deserialized_m2_result_cannot_authorize():
    task = _plan()
    genuine = validated_intent_for_plan(task)
    payload = genuine.model_dump(mode="json")
    restored = ValidatedIntentResult.model_validate(payload)

    assert not restored.is_m2_validated()
    authorization = TaskAuthorizationManager().authorize_step(
        task, restored, "step_001", scope=_scope()
    )
    assert authorization.decision == PermissionDecision.DENY


def test_forged_m2_result_cannot_indirectly_produce_capability():
    task = _plan()
    forged = ValidatedIntentResult(
        task_id=task.task_id,
        consistent=True,
        reason="forged",
        mismatched_steps=[],
    )
    authorization = TaskAuthorizationManager().authorize_step(
        task, forged, "step_001", scope=_scope()
    )

    with pytest.raises(CapabilityMintingError):
        _minter().mint(authorization, task, task.steps[0])


def test_validated_intent_result_has_no_public_issuance_classmethod():
    assert not hasattr(ValidatedIntentResult, "_from_validator")


def test_intent_check_result_cast_cannot_authorize():
    task = _plan()
    base = IntentCheckResult(
        task_id=task.task_id,
        consistent=True,
        reason="looks valid",
        mismatched_steps=[],
    )
    authorization = TaskAuthorizationManager().authorize_step(
        task, base, "step_001", scope=_scope()
    )
    assert authorization.decision == PermissionDecision.DENY


# --- M5-002: Key ownership ---


def test_production_minter_rejects_caller_supplied_secret_key():
    with pytest.raises(TypeError):
        CapabilityMinter(b"0123456789abcdef0123456789abcdef")


def test_production_key_provider_is_m5_owned():
    provider = CapabilityKeyProvider()
    assert provider._owned is True
    assert len(provider.get_signing_key()) >= 32


def test_test_key_provider_is_deterministic():
    first = CapabilityKeyProvider.for_testing(KEY)
    second = CapabilityKeyProvider.for_testing(KEY)
    assert first.get_signing_key() == second.get_signing_key()


# --- M5-003: Policy immutability ---


def test_policy_mutation_after_construction_fails():
    policy = CapabilityMintingPolicy()
    minter = CapabilityMinter(
        key_provider=CapabilityKeyProvider.for_testing(KEY),
        policy=policy,
    )

    with pytest.raises(Exception):
        minter.policy.lifetime = CapabilityMintingPolicy(lifetime=__import__("datetime").timedelta(hours=2)).lifetime

    task = _plan()
    capability = minter.mint(_genuine_authorization(task), task, task.steps[0])
    assert capability.claims.usage_policy.value == "ONE_TIME"


def test_external_input_does_not_alter_stored_policy():
    from datetime import timedelta

    external = {"lifetime": timedelta(hours=1), "usage_policy": "REPEATABLE"}
    policy = CapabilityMintingPolicy.model_validate(external)
    external["lifetime"] = timedelta(days=1)

    assert policy.lifetime == timedelta(hours=1)


# --- M5-006: Deserialization is not verification ---


def test_deserialized_capability_does_not_self_verify():
    task = _plan()
    capability = _minter().mint(_genuine_authorization(task), task, task.steps[0])
    payload = capability.model_dump(mode="json")
    payload["mac"] = "0" * 64
    restored = AuthenticatedCapability.model_validate(payload)

    assert isinstance(restored, AuthenticatedCapability)
    assert not verify_mac(restored.claims, KEY, restored.mac)
    assert not hasattr(restored, "verify")


# --- End-to-end substitution attacks ---


def test_task_substitution_attack_fails():
    task = _plan()
    authorization = _genuine_authorization(task)
    mutated = task.model_copy(deep=True, update={"task_id": "task_999"})

    with pytest.raises(CapabilityMintingError):
        _minter().mint(authorization, mutated, mutated.steps[0])


@pytest.mark.parametrize(
    "field,value",
    [
        ("step_id", "step_999"),
        ("resource", "secret.pdf"),
        ("operation", "DELETE"),
        ("agent", "shell_agent"),
    ],
)
def test_step_substitution_attacks_fail(field, value):
    task = _plan()
    authorization = _genuine_authorization(task)
    mutated = task.model_copy(deep=True)
    step = mutated.steps[0].model_copy(update={field: value})

    with pytest.raises(CapabilityMintingError):
        _minter().mint(authorization, mutated, step)


def test_constraint_substitution_cannot_mint():
    task = _plan()
    authorization = _genuine_authorization(task)
    tampered_step = task.steps[0].model_copy(update={"parameters": {"mode": "delete"}})

    with pytest.raises(CapabilityMintingError):
        _minter().mint(authorization, task, tampered_step)


def test_complete_m1_to_m5_lifecycle_flow_stops_before_execution():
    task = _plan()
    authorization = _genuine_authorization(task)
    authenticated = _minter().mint(authorization, task, task.steps[0])
    verified = CapabilityVerifier(
        key_provider=CapabilityKeyProvider.for_testing(KEY)
    ).verify(
        authenticated,
        expected_task_id=task.task_id,
        expected_step_id=task.steps[0].step_id,
        expected_agent=task.steps[0].agent,
        expected_operation=task.steps[0].operation,
        expected_resource=task.steps[0].resource,
        expected_scope=authorization.scope,
    )
    lifecycle = CapabilityLifecycleStore()

    assert lifecycle.verify_and_consume(verified) is verified
    assert not hasattr(verified, "execute")


def test_serialized_tampered_capability_cannot_reach_lifecycle():
    task = _plan()
    authenticated = _minter().mint(_genuine_authorization(task), task, task.steps[0])
    payload = authenticated.model_dump(mode="json")
    payload["claims"]["resource"] = "secret.pdf"

    with pytest.raises(Exception):
        CapabilityVerifier(key_provider=CapabilityKeyProvider.for_testing(KEY)).verify(payload)
