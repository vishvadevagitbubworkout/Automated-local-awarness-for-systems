import pytest

from app.capabilities.registry import CapabilityRegistry
from app.capabilities.templates import FILE_DELETE, FILE_READ, ResourceType, RiskLevel
from app.permissions.evaluator import PermissionEvaluator
from app.permissions.policies import (
    PermissionDecision,
    PermissionPolicy,
    PermissionPolicyRegistry,
    PermissionScope,
    PermissionScopeKind,
)


def read_scope(resource_id="report.pdf"):
    return PermissionScope(
        resource_type=ResourceType.FILE,
        kind=PermissionScopeKind.TASK,
        selector="current_task.resource",
        resource_id=resource_id,
    )


def make_policy(
    *,
    capability_id="file.read",
    permission_id="permission.file.read",
    operation="READ",
    decision=PermissionDecision.ALLOW,
    scope=None,
    risk_level=RiskLevel.LOW,
):
    return PermissionPolicy(
        permission_id=permission_id,
        capability_id=capability_id,
        resource_type=ResourceType.FILE,
        operation=operation,
        scope=scope or read_scope(),
        risk_level=risk_level,
        decision=decision,
    )


def evaluate_read(**overrides):
    values = {
        "capability": FILE_READ,
        "agent": "file_manager",
        "operation": "READ",
        "resource_type": ResourceType.FILE,
        "scope": read_scope(),
        "parameters": {"mode": "read"},
        "resource": "report.pdf",
    }
    values.update(overrides)
    return PermissionEvaluator().evaluate(**values)


def test_matching_approved_capability_and_policy_allows():
    assert evaluate_read() == PermissionDecision.ALLOW


def test_policy_deny_is_respected():
    registry = PermissionPolicyRegistry(
        [make_policy(decision=PermissionDecision.DENY)]
    )

    result = PermissionEvaluator(policy_registry=registry).evaluate(
        FILE_READ,
        agent="file_manager",
        operation="READ",
        resource_type=ResourceType.FILE,
        scope=read_scope(),
        parameters={"mode": "read"},
        resource="report.pdf",
    )

    assert result == PermissionDecision.DENY


def test_unknown_capability_is_denied():
    from app.capabilities.templates import CapabilityTemplateDefinition

    unknown = CapabilityTemplateDefinition(
        capability_id="file.format_disk",
        agent="file_manager",
        operation="FORMAT",
        resource_type=ResourceType.FILE,
        parameters={"mode": "format"},
        risk_level=RiskLevel.HIGH,
        description="Unknown capability.",
    )

    assert evaluate_read(capability=unknown, operation="FORMAT", parameters={"mode": "format"}) == PermissionDecision.DENY


def test_missing_policy_is_denied():
    empty_policies = PermissionPolicyRegistry([])

    result = PermissionEvaluator(policy_registry=empty_policies).evaluate(
        FILE_READ,
        agent="file_manager",
        operation="READ",
        resource_type=ResourceType.FILE,
        scope=read_scope(),
        parameters={"mode": "read"},
        resource="report.pdf",
    )

    assert result == PermissionDecision.DENY


def test_invalid_policy_provider_is_denied():
    class InvalidPolicyProvider:
        def list(self):
            return [object()]

    result = PermissionEvaluator(policy_registry=InvalidPolicyProvider()).evaluate(
        FILE_READ,
        agent="file_manager",
        operation="READ",
        resource_type=ResourceType.FILE,
        scope=read_scope(),
        parameters={"mode": "read"},
        resource="report.pdf",
    )

    assert result == PermissionDecision.DENY


def test_operation_mismatch_is_denied():
    assert evaluate_read(operation="DELETE") == PermissionDecision.DENY
    assert evaluate_read(
        capability=FILE_DELETE,
        operation="READ",
        parameters={"mode": "delete"},
    ) == PermissionDecision.DENY


def test_resource_type_mismatch_is_denied():
    assert evaluate_read(resource_type=ResourceType.DIRECTORY) == PermissionDecision.DENY


def test_scope_outside_policy_is_denied():
    outside_scope = PermissionScope(
        resource_type=ResourceType.FILE,
        kind=PermissionScopeKind.RESOURCE,
        selector="other_task.resource",
        resource_id="report.pdf",
    )

    assert evaluate_read(scope=outside_scope) == PermissionDecision.DENY


def test_missing_scope_is_denied():
    assert evaluate_read(scope=None) == PermissionDecision.DENY


def test_missing_resource_id_is_denied():
    scope_without_resource = PermissionScope(
        resource_type=ResourceType.FILE,
        kind=PermissionScopeKind.TASK,
        selector="current_task.resource",
    )

    assert evaluate_read(scope=scope_without_resource) == PermissionDecision.DENY


def test_different_resource_id_is_denied():
    assert evaluate_read(scope=read_scope("secret.pdf"), resource="report.pdf") == PermissionDecision.DENY


def test_exact_resource_match_allows():
    assert evaluate_read(scope=read_scope("report.pdf"), resource="report.pdf") == PermissionDecision.ALLOW


def test_resource_substitution_in_scope_is_denied():
    assert evaluate_read(scope=read_scope("other.pdf"), resource="other.pdf") == PermissionDecision.ALLOW
    assert evaluate_read(scope=read_scope("other.pdf"), resource="report.pdf") == PermissionDecision.DENY


def test_wrong_agent_is_denied():
    assert evaluate_read(agent="browser_agent") == PermissionDecision.DENY


def test_extra_privilege_parameters_are_denied():
    assert evaluate_read(parameters={"mode": "read", "execute": True}) == PermissionDecision.DENY


def test_altered_capability_is_denied():
    altered = FILE_READ.model_copy(deep=True)
    altered.operation = "DELETE"

    assert evaluate_read(capability=altered) == PermissionDecision.DENY


def test_arbitrary_llm_capability_is_denied():
    from app.capabilities.templates import CapabilityTemplateDefinition

    arbitrary = CapabilityTemplateDefinition(
        capability_id="admin.execute",
        agent="admin_agent",
        operation="EXECUTE",
        resource_type=ResourceType.FILE,
        parameters={"mode": "execute"},
        risk_level=RiskLevel.HIGH,
        description="LLM-created capability.",
    )

    assert evaluate_read(capability=arbitrary, operation="EXECUTE", parameters={"mode": "execute"}) == PermissionDecision.DENY


def test_evaluation_is_deterministic():
    results = [evaluate_read() for _ in range(3)]

    assert results == [PermissionDecision.ALLOW] * 3


def test_evaluator_does_not_execute_operations_or_modify_policy():
    policy_registry = PermissionPolicyRegistry()
    evaluator = PermissionEvaluator(policy_registry=policy_registry)

    assert not hasattr(evaluator, "execute")
    assert not hasattr(evaluator, "run")
    before = policy_registry.get("permission.file.read")
    evaluator.evaluate(
        FILE_READ,
        agent="file_manager",
        operation="READ",
        resource_type=ResourceType.FILE,
        scope=read_scope(),
        parameters={"mode": "read"},
        resource="report.pdf",
    )
    after = policy_registry.get("permission.file.read")
    assert before == after
