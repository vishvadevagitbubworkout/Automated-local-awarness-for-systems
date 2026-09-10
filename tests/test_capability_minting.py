from datetime import timedelta

import pytest
from pydantic import ValidationError

from app.capabilities.templates import ResourceType
from app.permissions.authorization import AuthorizationResult, TaskAuthorizationManager
from app.permissions.policies import PermissionDecision, PermissionScope, PermissionScopeKind
from app.planner.schemas import PlanStep, TaskPlan
from app.security.capabilities import AuthenticatedCapability, UsagePolicy
from app.security.crypto import verify_mac
from app.security.key_provider import CapabilityKeyProvider
from app.security.minting import CapabilityMinter, CapabilityMintingError, CapabilityMintingPolicy
from tests.support import validated_intent_for_plan

KEY = b"0123456789abcdef0123456789abcdef"


def make_test_key_provider():
    return CapabilityKeyProvider.for_testing(KEY)


def scope(resource="report.pdf"):
    return PermissionScope(
        resource_type=ResourceType.FILE,
        kind=PermissionScopeKind.TASK,
        selector="current_task.resource",
        resource_id=resource,
    )


def plan(task_id="task_001", resource="report.pdf", operation="READ", step_id="step_001"):
    return TaskPlan(
        task_id=task_id,
        original_request="Read report.pdf",
        steps=[
            PlanStep(
                step_id=step_id,
                agent="file_manager",
                operation=operation,
                resource=resource,
                parameters={"mode": operation.lower()},
                template="FILE_READ",
                intent="READ",
            )
        ],
    )


def allowed(task=None):
    task = task or plan()
    return TaskAuthorizationManager().authorize_step(
        task,
        validated_intent_for_plan(task),
        task.steps[0].step_id,
        scope=scope(task.steps[0].resource),
    )


def minter():
    return CapabilityMinter(key_provider=make_test_key_provider())


def test_allow_mints_authenticated_capability():
    task = plan()
    authorization = allowed(task)

    capability = minter().mint(authorization, task, task.steps[0])

    assert isinstance(capability, AuthenticatedCapability)
    assert capability.claims.task_id == "task_001"
    assert capability.claims.step_id == "step_001"
    assert capability.claims.capability_id == "file.read"
    assert capability.claims.resource == "report.pdf"
    assert capability.mac
    assert verify_mac(capability.claims, KEY, capability.mac)


def test_deny_cannot_mint():
    task = plan(operation="FORMAT")
    authorization = TaskAuthorizationManager().authorize_step(
        task,
        validated_intent_for_plan(task),
        "step_001",
        scope=scope(),
    )

    assert authorization.decision == PermissionDecision.DENY
    with pytest.raises(CapabilityMintingError, match="ALLOW"):
        minter().mint(authorization, task, task.steps[0])


def test_forged_authorization_cannot_mint():
    task = plan()
    forged = AuthorizationResult(
        task_id=task.task_id,
        step_id="step_001",
        capability_id="file.read",
        decision=PermissionDecision.ALLOW,
        scope=scope(),
        reason="forged",
    )

    with pytest.raises(CapabilityMintingError, match="integrity"):
        minter().mint(forged, task, task.steps[0])


def test_task_mismatch_is_rejected():
    task = plan(task_id="task_002")
    authorization = allowed(plan(task_id="task_001"))

    with pytest.raises(CapabilityMintingError, match="task"):
        minter().mint(authorization, task, task.steps[0])


def test_step_mismatch_is_rejected():
    task = plan()
    other_step = task.steps[0].model_copy(update={"step_id": "step_002"})

    with pytest.raises(CapabilityMintingError, match="step"):
        minter().mint(allowed(task), task, other_step)


def test_resource_substitution_is_rejected():
    task = plan(resource="secret.pdf")

    with pytest.raises(CapabilityMintingError, match="scope"):
        minter().mint(allowed(plan()), task, task.steps[0])


def test_operation_substitution_is_rejected():
    task = plan(operation="DELETE")
    authorization = allowed(plan())

    with pytest.raises(CapabilityMintingError):
        minter().mint(authorization, task, task.steps[0])


def test_agent_substitution_is_rejected():
    task = plan()
    changed_step = task.steps[0].model_copy(update={"agent": "shell_agent"})

    with pytest.raises(CapabilityMintingError, match="step"):
        minter().mint(allowed(task), task, changed_step)


def test_each_mint_gets_a_fresh_nonce():
    task = plan()
    mint = minter()

    first = mint.mint(allowed(task), task, task.steps[0])
    second = mint.mint(allowed(task), task, task.steps[0])

    assert first.claims.nonce != second.claims.nonce
    assert first.mac != second.mac


def test_expiry_is_m5_controlled_and_bounded():
    with pytest.raises(ValueError):
        CapabilityMintingPolicy(lifetime=timedelta(days=365))

    task = plan()
    capability = minter().mint(allowed(task), task, task.steps[0])
    lifetime = capability.claims.expires_at - capability.claims.issued_at
    assert lifetime == timedelta(minutes=5)


def test_claims_inherit_exact_authorized_values():
    task = plan()
    authorization = allowed(task)
    capability = minter().mint(authorization, task, task.steps[0])

    assert capability.claims.task_id == authorization.task_id
    assert capability.claims.step_id == authorization.step_id
    assert capability.claims.scope == authorization.scope
    assert capability.claims.agent == task.steps[0].agent
    assert capability.claims.operation == task.steps[0].operation
    assert dict(capability.claims.constraints) == {"mode": "read"}
    assert capability.claims.usage_policy == UsagePolicy.ONE_TIME


def test_authenticated_capability_is_immutable_and_not_retaggable():
    task = plan()
    capability = minter().mint(allowed(task), task, task.steps[0])

    with pytest.raises(ValidationError):
        capability.mac = "0" * 64
    with pytest.raises(TypeError, match="retagged"):
        capability.model_copy(update={"claims": capability.claims, "mac": "0" * 64})
    with pytest.raises(TypeError, match="retagged"):
        capability.claims.model_copy(update={"task_id": "task_999"})


def test_production_minter_uses_m5_owned_key_provider():
    production = CapabilityMinter()
    assert production._key_provider._owned is True


def test_caller_cannot_replace_production_key_through_public_api():
    with pytest.raises(TypeError):
        CapabilityMinter(KEY)


def test_wrong_key_fails_verification():
    task = plan()
    capability = minter().mint(allowed(task), task, task.steps[0])
    wrong_key = b"fedcba9876543210fedcba9876543210"

    assert not verify_mac(capability.claims, wrong_key, capability.mac)


def test_serialized_capability_does_not_contain_secret():
    task = plan()
    capability = minter().mint(allowed(task), task, task.steps[0])
    serialized = capability.model_dump(mode="json")

    assert KEY.decode() not in str(serialized)
    assert "secret_key" not in serialized


def test_minting_policy_is_immutable():
    policy = CapabilityMintingPolicy()

    with pytest.raises(ValidationError):
        policy.lifetime = timedelta(hours=2)

    with pytest.raises(ValidationError):
        policy.usage_policy = UsagePolicy.REPEATABLE


def test_minting_does_not_expose_lifecycle_or_execution_behavior():
    task = plan()
    capability = minter().mint(allowed(task), task, task.steps[0])

    assert not hasattr(capability, "consume")
    assert not hasattr(capability, "state")
    assert not hasattr(capability, "verify")
    assert not hasattr(capability, "execute")
