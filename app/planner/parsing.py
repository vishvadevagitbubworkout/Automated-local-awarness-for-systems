import json

from pydantic import ValidationError

from app.planner.schemas import TaskPlan


class PlanParsingError(ValueError):
    """Raised when model output cannot become a complete TaskPlan."""


def parse_task_plan(raw_response: str) -> TaskPlan:
    if not isinstance(raw_response, str) or not raw_response.strip():
        raise PlanParsingError("The model returned an empty planning response.")

    try:
        payload = json.loads(raw_response)
    except json.JSONDecodeError as error:
        raise PlanParsingError("The model returned invalid JSON.") from error

    if not isinstance(payload, dict):
        raise PlanParsingError("The planning response must be a JSON object.")

    try:
        if hasattr(TaskPlan, "model_validate"):
            plan = TaskPlan.model_validate(payload)
        else:
            plan = TaskPlan.parse_obj(payload)
    except ValidationError as error:
        raise PlanParsingError(
            f"The planning response does not match TaskPlan: {error}"
        ) from error

    if not plan.task_id.strip():
        raise PlanParsingError("The planning response has no task ID.")
    if not plan.original_request.strip():
        raise PlanParsingError("The planning response has no original request.")
    if not plan.steps:
        raise PlanParsingError("The planning response contains no steps.")

    for step in plan.steps:
        if not step.step_id.strip():
            raise PlanParsingError("A planning step has no step ID.")
        if not step.agent.strip():
            raise PlanParsingError("A planning step has no agent.")
        if not step.operation.strip():
            raise PlanParsingError("A planning step has no operation.")

    return plan