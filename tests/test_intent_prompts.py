from app.intent.prompts import build_intent_prompt
from app.planner.schemas import PlanStep, TaskPlan


def test_intent_prompt_contains_plan_and_m2_boundary():
    task_plan = TaskPlan(
        task_id="task_001",
        original_request="Create rest.pdf in Documents.",
        steps=[
            PlanStep(
                step_id="step_001",
                agent="file_manager",
                operation="create_file",
                resource="rest.pdf",
                parameters={"location": "Documents"},
            )
        ],
    )

    prompt = build_intent_prompt(task_plan)

    assert "Create rest.pdf in Documents." in prompt
    assert "file_manager" in prompt
    assert "create_file" in prompt
    assert "task-intent consistency" in prompt
    assert "Return exactly one valid JSON object" in prompt
    assert "Do not make authorization decisions" in prompt
    assert "Do not execute actions" in prompt