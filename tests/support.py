import json

from app.intent.validator import IntentValidator
from app.planner.schemas import TaskPlan


class FakeOllamaClient:
    def __init__(self, response: str):
        self.response = response
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response


def validated_intent_for_plan(
    plan: TaskPlan,
    *,
    consistent: bool = True,
    reason: str = "The plan matches the request.",
    mismatched_steps: list[str] | None = None,
):
    """Obtain a genuine M2-validated result through the public validator API."""
    payload = {
        "task_id": plan.task_id,
        "consistent": consistent,
        "reason": reason,
        "mismatched_steps": mismatched_steps or [],
    }
    return IntentValidator(FakeOllamaClient(json.dumps(payload))).validate(plan)
