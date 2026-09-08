import pytest

from app.intent.parsing import IntentParsingError, parse_intent_result


def test_parse_intent_result_validates_expected_output():
    result = parse_intent_result(
        '{"task_id":"task_001","consistent":true,'
        '"reason":"The step matches the request.","mismatched_steps":[]}'
    )

    assert result.task_id == "task_001"
    assert result.consistent is True


@pytest.mark.parametrize(
    "raw_response, expected_message",
    [
        ("", "empty response"),
        ("{this is not valid json", "invalid JSON"),
        ("[]", "JSON object"),
        (
            '{"task_id":"task_001","consistent":true}',
            "does not match IntentCheckResult",
        ),
        (
            '{"task_id":"task_001","consistent":"yes",'
            '"reason":"test","mismatched_steps":[]}',
            "does not match IntentCheckResult",
        ),
        (
            '{"task_id":"task_001","consistent":true,"reason":"test",'
            '"mismatched_steps":[2]}',
            "does not match IntentCheckResult",
        ),
    ],
)
def test_parse_intent_result_rejects_malformed_output(raw_response, expected_message):
    with pytest.raises(IntentParsingError, match=expected_message):
        parse_intent_result(raw_response)