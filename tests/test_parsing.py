import json

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


def test_low_confidence_step_routes_to_clarification():
    plan = parse_task_plan(
        '{"task_id":"task_001","original_request":"Find the invoice",'
        '"steps":[{"step_id":"step_001","agent":"file_agent",'
        '"operation":"LIST","intent":"READ","confidence":0.69}]}'
    )

    assert plan.steps[0].intent.value == "ASK_CLARIFICATION"


def test_valid_intent_and_normal_confidence_are_preserved():
    plan = parse_task_plan(
        '{"task_id":"task_001","original_request":"Read report.pdf",'
        '"steps":[{"step_id":"step_001","agent":"file_agent",'
        '"operation":"READ","intent":"READ","confidence":0.95}]}'
    )

    assert plan.steps[0].intent.value == "READ"
    assert plan.steps[0].confidence == 0.95


def test_invalid_planner_intent_is_rejected():
    with pytest.raises(PlanParsingError, match="does not match TaskPlan"):
        parse_task_plan(
            '{"task_id":"task_001","original_request":"Read report",'
            '"steps":[{"step_id":"step_001","agent":"file_agent",'
            '"operation":"READ","intent":"DELETE"}]}'
        )


@pytest.mark.parametrize("resource", ["C:\\Users\\user\\secret.txt", "/tmp/secret.txt"])
def test_absolute_resource_path_is_rejected(resource):
    with pytest.raises(PlanParsingError, match="absolute filesystem path"):
        parse_task_plan(
            json.dumps(
                {
                    "task_id": "task_001",
                    "original_request": "Read a file",
                    "steps": [
                        {
                            "step_id": "step_001",
                            "agent": "file_agent",
                            "operation": "READ",
                            "resource": resource,
                        }
                    ],
                }
            )
        )


@pytest.mark.parametrize("operation", ["powershell Get-ChildItem", "rm -rf secret.txt"])
def test_raw_shell_command_is_rejected(operation):
    with pytest.raises(PlanParsingError, match="raw shell command"):
        parse_task_plan(
            json.dumps(
                {
                    "task_id": "task_001",
                    "original_request": "Run a command",
                    "steps": [
                        {
                            "step_id": "step_001",
                            "agent": "shell_agent",
                            "operation": operation,
                        }
                    ],
                }
            )
        )