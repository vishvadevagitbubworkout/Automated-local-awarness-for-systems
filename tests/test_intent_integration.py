import pytest

from app.intent.validator import IntentValidator
from app.planner.ollama_client import OllamaError
from app.planner.schemas import PlanStep, TaskPlan


@pytest.mark.integration
def test_intent_validator_with_local_ollama():
    task_plan = TaskPlan(
        task_id="integration_task_001",
        original_request="Read report.pdf from Documents.",
        steps=[
            PlanStep(
                step_id="step_001",
                agent="file_manager",
                operation="read_file",
                resource="report.pdf",
                parameters={"location": "Documents"},
            )
        ],
    )

    try:
        result = IntentValidator().validate(task_plan)
    except OllamaError as error:
        pytest.skip(f"Local Ollama unavailable: {error}")

    assert result.task_id == task_plan.task_id
    assert isinstance(result.consistent, bool)
    assert isinstance(result.reason, str)
    assert isinstance(result.mismatched_steps, list)