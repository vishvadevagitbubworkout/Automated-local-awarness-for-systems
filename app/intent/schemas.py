import hashlib
import json

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, StrictBool, StrictStr

_M2_VALIDATION_TOKEN = object()
_M2_ISSUER = object()


def _plan_digest(task_plan) -> str:
    payload = task_plan.model_dump(mode="json")
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class IntentCheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: StrictStr
    consistent: StrictBool
    reason: StrictStr
    mismatched_steps: list[StrictStr] = Field(default_factory=list)


class ValidatedIntentResult(IntentCheckResult):
    """M2-issued result carrying an in-process validation provenance marker."""

    _validation_token: object | None = PrivateAttr(default=None)
    _validated_plan_digest: str | None = PrivateAttr(default=None)

    @classmethod
    def _from_validator(
        cls,
        result: IntentCheckResult,
        task_plan,
        issuer,
    ) -> "ValidatedIntentResult":
        if issuer is not _M2_ISSUER:
            raise TypeError("Only the M2 validator may issue a validated intent result.")
        validated = cls.model_validate(result.model_dump())
        validated._validation_token = _M2_VALIDATION_TOKEN
        validated._validated_plan_digest = _plan_digest(task_plan)
        return validated

    def is_m2_validated(self) -> bool:
        return self._validation_token is _M2_VALIDATION_TOKEN

    def is_bound_to_plan(self, task_plan) -> bool:
        return (
            self.is_m2_validated()
            and self.task_id == task_plan.task_id
            and self._validated_plan_digest == _plan_digest(task_plan)
        )

    def model_copy(self, *, update=None, deep=False):
        if update:
            raise TypeError("ValidatedIntentResult cannot be retagged after M2 validation.")
        return super().model_copy(update=None, deep=deep)