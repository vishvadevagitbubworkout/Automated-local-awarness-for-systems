from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictStr


class IntentCheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: StrictStr
    consistent: StrictBool
    reason: StrictStr
    mismatched_steps: list[StrictStr] = Field(default_factory=list)