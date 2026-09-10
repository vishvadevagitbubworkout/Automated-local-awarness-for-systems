import pytest

from app.capabilities.templates import ResourceType
from app.intent.schemas import IntentCheckResult, ValidatedIntentResult, _M2_ISSUER
from app.permissions.authorization import AuthorizationResult, TaskAuthorizationManager
from app.permissions.policies import PermissionDecision, PermissionScope, PermissionScopeKind
from app.planner.schemas import PlanStep, TaskPlan


def task_scope(selector="current_task.resource"):
    return PermissionScope(
        resource_type=ResourceType.FILE,
        kind=PermissionScopeKind.TASK,
        selector=selector,
        resource_id="report.pdf",
    )


def make_plan(task_id="task_001", operation="READ", step_id="step_001"):
    return TaskPlan(
        task_id=task_id,
        original_request="Read report.pdf",
        steps=[
            PlanStep(
                step_id=step_id,
                agent="file_manager",
                operation=operation,
                resource="report.pdf",
                parameters={"mode": operation.lower()},
                template="FILE_READ",
                intent="READ",
            )
        ],
    )


def make_result(task_id="task_001", consistent=True, mismatched_steps=None, plan=None):
    plan = plan or make_plan(task_id=task_id)
    return ValidatedIntentResult._from_validator(IntentCheckResult(
        task_id=task_id,
        consistent=consistent,
        reason="The plan matches the request." if consistent else "The plan is inconsistent.",
        mismatched_steps=mismatched_steps or [],
    ), plan, _M2_ISSUER)


def test_valid_m2_m3_m4_flow_allows_for_task_and_step():
    result = TaskAuthorizationManager().authorize_step(
        make_plan(),
        make_result(),
        "step_001",
        scope=task_scope(),
    )

    assert result.task_id == "task_001"
    assert result.step_id == "step_001"
    assert result.capability_id == "file.read"
    assert result.decision == PermissionDecision.ALLOW
    assert result.scope == task_scope()
    assert result.is_integrity_valid()
    assert result.is_bound_to("task_001", "step_001")


def test_mismatched_m2_task_id_is_denied():
    result = TaskAuthorizationManager().authorize_step(
        make_plan(task_id="task_001"),
        make_result(task_id="task_999"),
        "step_001",
        scope=task_scope(),
    )

    assert result.decision == PermissionDecision.DENY
    assert "task identity" in result.reason


def test_forged_base_intent_result_is_denied():
    forged = IntentCheckResult(
        task_id="task_001",
        consistent=True,
        reason="caller assertion",
        mismatched_steps=[],
    )

    result = TaskAuthorizationManager().authorize_step(
        make_plan(),
        forged,
        "step_001",
        scope=task_scope(),
    )

    assert result.decision == PermissionDecision.DENY


def test_untrusted_caller_cannot_issue_validated_intent_artifact():
    with pytest.raises(TypeError, match="Only the M2 validator"):
        ValidatedIntentResult._from_validator(
            IntentCheckResult(
                task_id="task_001",
                consistent=True,
                reason="caller assertion",
                mismatched_steps=[],
            ),
            make_plan(),
            object(),
        )


def test_missing_task_id_is_denied():
    result = TaskAuthorizationManager().authorize_step(
        make_plan(task_id=""),
        make_result(task_id=""),
        "step_001",
        scope=task_scope(),
    )

    assert result.decision == PermissionDecision.DENY
    assert result.task_id == ""


def test_wrong_step_id_is_denied():
    result = TaskAuthorizationManager().authorize_step(
        make_plan(),
        make_result(),
        "step_999",
        scope=task_scope(),
    )

    assert result.decision == PermissionDecision.DENY
    assert "not part" in result.reason


def test_mismatched_m2_step_is_denied():
    result = TaskAuthorizationManager().authorize_step(
        make_plan(),
        make_result(mismatched_steps=["step_001"]),
        "step_001",
        scope=task_scope(),
    )

    assert result.decision == PermissionDecision.DENY


def test_missing_scope_is_denied():
    result = TaskAuthorizationManager().authorize_step(
        make_plan(),
        make_result(),
        "step_001",
        scope=None,
    )

    assert result.decision == PermissionDecision.DENY
    assert "scope" in result.reason


def test_broadened_scope_is_denied():
    result = TaskAuthorizationManager().authorize_step(
        make_plan(),
        make_result(),
        "step_001",
        scope=task_scope("entire_filesystem"),
    )

    assert result.decision == PermissionDecision.DENY


def test_scope_resource_broadening_is_denied():
    broadened = PermissionScope(
        resource_type=ResourceType.FILE,
        kind=PermissionScopeKind.TASK,
        selector="current_task.resource",
        resource_id="entire Documents",
    )

    result = TaskAuthorizationManager().authorize_step(
        make_plan(),
        make_result(),
        "step_001",
        scope=broadened,
    )

    assert result.decision == PermissionDecision.DENY


def test_unresolved_m3_capability_is_denied():
    result = TaskAuthorizationManager().authorize_step(
        make_plan(operation="FORMAT"),
        make_result(),
        "step_001",
        scope=task_scope(),
    )

    assert result.decision == PermissionDecision.DENY
    assert result.capability_id is None


def test_inconsistent_m2_result_cannot_reach_allow():
    result = TaskAuthorizationManager().authorize_step(
        make_plan(),
        make_result(consistent=False),
        "step_001",
        scope=task_scope(),
    )

    assert result.decision == PermissionDecision.DENY


def test_authorization_result_cannot_be_reused_for_another_task_or_step():
    result = TaskAuthorizationManager().authorize_step(
        make_plan(),
        make_result(),
        "step_001",
        scope=task_scope(),
    )

    assert result.is_bound_to("task_001", "step_001")
    assert not result.is_bound_to("task_002", "step_001")
    assert not result.is_bound_to("task_001", "step_002")


def test_plan_authorizes_steps_independently():
    plan = TaskPlan(
        task_id="task_001",
        original_request="Read and format report.pdf",
        steps=[
            PlanStep(
                step_id="step_read",
                agent="file_manager",
                operation="READ",
                resource="report.pdf",
                parameters={"mode": "read"},
                template="FILE_READ",
                intent="READ",
            ),
            PlanStep(
                step_id="step_format",
                agent="file_manager",
                operation="FORMAT",
                resource="report.pdf",
                parameters={"mode": "format"},
                template="FILE_READ",
                intent="READ",
            ),
        ],
    )
    results = TaskAuthorizationManager().authorize_plan(
        plan,
        make_result(plan=plan),
        {"step_read": task_scope(), "step_format": task_scope()},
    )

    assert [result.decision for result in results] == [
        PermissionDecision.ALLOW,
        PermissionDecision.DENY,
    ]
    assert [result.step_id for result in results] == ["step_read", "step_format"]


def test_authorization_result_is_immutable_and_data_only():
    result = TaskAuthorizationManager().authorize_step(
        make_plan(),
        make_result(),
        "step_001",
        scope=task_scope(),
    )

    with pytest.raises(Exception):
        result.task_id = "task_002"
    with pytest.raises(TypeError, match="retagged"):
        result.model_copy(update={"task_id": "task_002"})
    assert result.is_integrity_valid()
    assert not hasattr(result, "execute")
    assert not hasattr(result, "run")
