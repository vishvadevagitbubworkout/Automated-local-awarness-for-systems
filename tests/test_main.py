from app.main import format_plan
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