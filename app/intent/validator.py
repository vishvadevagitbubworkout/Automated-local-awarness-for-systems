from app.intent.parsing import parse_intent_result
from app.intent.prompts import build_intent_prompt
from app.intent.schemas import IntentCheckResult
from app.planner.ollama_client import OllamaClient
from app.planner.schemas import TaskPlan


class IntentValidator:
    """Check whether a TaskPlan represents its original user request."""

    def __init__(self, ollama_client: OllamaClient | None = None):
        self.ollama_client = ollama_client or OllamaClient()

    def validate(self, task_plan: TaskPlan) -> IntentCheckResult:
        if not isinstance(task_plan, TaskPlan):
            raise TypeError("IntentValidator.validate expects a TaskPlan.")
        if not task_plan.task_id.strip():
            raise ValueError("The TaskPlan has no task ID.")
        if not task_plan.original_request.strip():
            raise ValueError("The TaskPlan has no original request.")

        for step in task_plan.steps:
            if not step.step_id.strip():
                raise ValueError("A TaskPlan step has no step ID.")
            if not step.agent.strip():
                raise ValueError("A TaskPlan step has no agent.")
            if not step.operation.strip():
                raise ValueError("A TaskPlan step has no operation.")

        if not task_plan.steps:
            return IntentCheckResult(
                task_id=task_plan.task_id,
                consistent=False,
                reason=(
                    "The plan contains no steps capable of fulfilling the "
                    "user's request."
                ),
                mismatched_steps=[],
            )

        raw_response = self.ollama_client.generate(build_intent_prompt(task_plan))
        result = parse_intent_result(raw_response)
        if result.task_id != task_plan.task_id:
            raise ValueError(
                "The intent response task ID does not match the supplied TaskPlan."
            )
        return result