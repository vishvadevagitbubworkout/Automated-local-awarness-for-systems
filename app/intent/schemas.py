import hashlib
import json

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, StrictBool, StrictStr


def _plan_digest(task_plan) -> str:
    payload = task_plan.model_dump(mode="json")
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _create_m2_validation_trust_boundary():
    """Closure-scoped issuance authority for M2 validated intent results."""
    _validation_token = object()

    def issue(result: "IntentCheckResult", task_plan) -> "ValidatedIntentResult":
        validated = ValidatedIntentResult.model_validate(result.model_dump())
        validated._validation_token = _validation_token
        validated._validated_plan_digest = _plan_digest(task_plan)
        return validated

    def is_m2_validated(result: "ValidatedIntentResult") -> bool:
        return getattr(result, "_validation_token", None) is _validation_token

    return issue, is_m2_validated


_issue_validated_intent, _validated_intent_is_m2_validated = _create_m2_validation_trust_boundary()


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

    def is_m2_validated(self) -> bool:
        return _validated_intent_is_m2_validated(self)

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
