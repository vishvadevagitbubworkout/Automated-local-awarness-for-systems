import pytest

from app.planner.parsing import PlanParsingError, parse_task_plan


def test_parse_task_plan_validates_json_into_task_plan():
    plan = parse_task_plan(
        '{"task_id":"task_001",'
        '"original_request":"Read report.pdf",'
        '"steps":[{"step_id":"step_001","agent":"file_agent",'
        '"operation":"READ","resource":"report.pdf",'
        '"parameters":{"location":"Documents"}}]}'
    )

    assert plan.task_id == "task_001"
    assert plan.steps[0].operation == "READ"


@pytest.mark.parametrize(
    "raw_response, expected_message",
    [
        ("not json", "invalid JSON"),
        ("[]", "JSON object"),
        ('{"task_id":"task_001"}', "does not match TaskPlan"),
        (
            '{"task_id":"task_001","original_request":"request","steps":[]}',
            "no steps",
        ),
        (
            '{"task_id":"","original_request":"request",'
            '"steps":[{"step_id":"step_001","agent":"file_agent",'
            '"operation":"READ"}]}',
            "no task ID",
        ),
    ],
)
def test_parse_task_plan_rejects_invalid_output(raw_response, expected_message):
    with pytest.raises(PlanParsingError, match=expected_message):
        parse_task_plan(raw_response)