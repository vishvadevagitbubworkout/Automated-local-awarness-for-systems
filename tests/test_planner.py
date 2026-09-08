from app.planner.schemas import TaskPlan, PlanStep


def test_task_plan():
    plan = TaskPlan(
        task_id="task_001",
        original_request="Read report.pdf from Documents",
        steps=[
            PlanStep(
                step_id="step_001",
                agent="file_agent",
                operation="READ",
                resource="report.pdf",
                parameters={
                    "location": "Documents"
                }
            )
        ]
    )

    assert plan.task_id == "task_001"
    assert len(plan.steps) == 1
    assert plan.steps[0].agent == "file_agent"
    assert plan.steps[0].operation == "READ"