from pydantic import BaseModel, Field
from typing import Any


class PlanStep(BaseModel):
    step_id: str
    agent: str
    operation: str
    resource: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class TaskPlan(BaseModel):
    task_id: str
    original_request: str
    steps: list[PlanStep]