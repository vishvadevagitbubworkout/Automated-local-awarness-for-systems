from app.capabilities.templates import FILE_READ
from app.main import format_capabilities
from app.main import format_authorization_results
from app.main import format_plan
from app.main import format_intent_result
from app.intent.schemas import IntentCheckResult
from app.planner.schemas import PlanStep, TaskPlan


def test_format_plan_displays_plan_without_execution():
    plan = TaskPlan(
        task_id="task_001",
        original_request="Read report.pdf from Documents",
        steps=[
            PlanStep(
                step_id="step_001",
                agent="file_agent",
                operation="READ",
                resource="report.pdf",
                parameters={"location": "Documents"},
            )
        ],
    )

    output = format_plan(plan)

    assert "Generated Plan:" in output
    assert "Agent: file_agent" in output
    assert "Operation: READ" in output
    assert "Template: legacy/unspecified" in output
    assert "location: Documents" in output


def test_format_intent_result_displays_consistency_status():
    output = format_intent_result(
        IntentCheckResult(
            task_id="task_001",
            consistent=False,
            reason="The browser action was not requested.",
            mismatched_steps=["step_002"],
        )
    )

    assert "Intent Validation:" in output
    assert "Status: INCONSISTENT" in output
    assert "Mismatched Steps:" in output
    assert "step_002" in output


def test_format_capabilities_displays_approved_ids_only():
    output = format_capabilities([FILE_READ])

    assert "Approved Capabilities:" in output


def test_format_authorization_results_displays_task_bound_decisions():
    from app.permissions.authorization import AuthorizationResult
    from app.permissions.policies import PermissionDecision, PermissionScope, PermissionScopeKind
    from app.capabilities.templates import ResourceType

    output = format_authorization_results(
        [
            AuthorizationResult(
                task_id="task_001",
                step_id="step_001",
                capability_id="file.read",
                decision=PermissionDecision.ALLOW,
                scope=PermissionScope(
                    resource_type=ResourceType.FILE,
                    kind=PermissionScopeKind.TASK,
                    selector="current_task.resource",
                ),
                reason="approved",
            )
        ]
    )

    assert "task_001/step_001: ALLOW (file.read)" in output