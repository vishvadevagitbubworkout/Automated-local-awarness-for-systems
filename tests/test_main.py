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