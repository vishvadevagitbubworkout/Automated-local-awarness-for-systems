import json

from pydantic import ValidationError

from app.intent.schemas import IntentCheckResult


class IntentParsingError(ValueError):
    """Raised when model output cannot become an IntentCheckResult."""


def _normalize_mismatched_steps(value):
    if not isinstance(value, list):
        return []
    normalized = []
    for item in value:
        if isinstance(item, str):
            normalized.append(item)
        elif isinstance(item, dict):
            for key in ("step_id", "id", "step"):
                candidate = item.get(key)
                if isinstance(candidate, str) and candidate.strip():
                    normalized.append(candidate)
                    break
            else:
                raise IntentParsingError(
                    "The intent response does not match IntentCheckResult: malformed mismatched step identifiers."
                )
        else:
            raise IntentParsingError(
                "The intent response does not match IntentCheckResult: malformed mismatched step identifiers."
            )
    return normalized


def parse_intent_result(raw_response: str) -> IntentCheckResult:
    if not isinstance(raw_response, str) or not raw_response.strip():
        raise IntentParsingError("The intent validator returned an empty response.")

    try:
        payload = json.loads(raw_response)
    except json.JSONDecodeError as error:
        raise IntentParsingError("The intent validator returned invalid JSON.") from error

    if not isinstance(payload, dict):
        raise IntentParsingError("The intent response must be a JSON object.")

    if "mismatched_steps" in payload:
        payload["mismatched_steps"] = _normalize_mismatched_steps(payload.get("mismatched_steps"))

    try:
        if hasattr(IntentCheckResult, "model_validate"):
            result = IntentCheckResult.model_validate(payload)
        else:
            result = IntentCheckResult.parse_obj(payload)
    except ValidationError as error:
        raise IntentParsingError(
            f"The intent response does not match IntentCheckResult: {error}"
        ) from error

    if not result.task_id.strip():
        raise IntentParsingError("The intent response has no task ID.")
    if not result.reason.strip():
        raise IntentParsingError("The intent response has no reason.")

    return result