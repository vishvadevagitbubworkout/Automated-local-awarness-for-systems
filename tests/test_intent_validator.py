import json

import pytest

from app.intent.parsing import IntentParsingError
from app.intent.validator import IntentValidator
from app.planner.schemas import PlanStep, TaskPlan


class FakeOllamaClient:
    def __init__(self, response):
        self.response = response
        self.prompts = []

    def generate(self, prompt):
        self.prompts.append(prompt)
        return self.response


def make_plan(*steps):
    return TaskPlan(
        task_id="task_001",
        original_request="Create rest.pdf in Documents.",
        steps=list(steps),
    )


def make_step(step_id, agent, operation, resource):
    return PlanStep(
        step_id=step_id,
        agent=agent,
        operation=operation,
        resource=resource,
    )


def make_result(consistent, reason, mismatched_steps):
    return json.dumps(
        {
            "task_id": "task_001",
            "consistent": consistent,
            "reason": reason,
            "mismatched_steps": mismatched_steps,
        }
    )


def test_matching_single_step_plan_is_consistent():
    plan = make_plan(make_step("step_001", "file_manager", "create_file", "rest.pdf"))
    validator = IntentValidator(
        FakeOllamaClient(make_result(True, "The file creation matches the request.", []))
    )

    result = validator.validate(plan)

    assert result.consistent is True
    assert result.mismatched_steps == []


def test_unrelated_browser_step_is_mismatched():
    plan = make_plan(
        make_step("step_001", "file_manager", "create_file", "rest.pdf"),
        make_step("step_002", "browser", "open_url", "google.com"),
    )
    validator = IntentValidator(
        FakeOllamaClient(
            make_result(False, "The browser action was not requested.", ["step_002"])
        )
    )

    result = validator.validate(plan)

    assert result.consistent is False
    assert result.mismatched_steps == ["step_002"]


def test_unrelated_email_step_is_mismatched():
    plan = make_plan(
        make_step("step_001", "file_manager", "create_file", "rest.pdf"),
        make_step("step_002", "email", "send_email", "example@example.com"),
    )
    validator = IntentValidator(
        FakeOllamaClient(
            make_result(False, "The email action was not requested.", ["step_002"])
        )
    )

    result = validator.validate(plan)

    assert result.consistent is False
    assert "step_002" in result.mismatched_steps


def test_legitimate_multi_agent_plan_is_consistent():
    plan = TaskPlan(
        task_id="task_001",
        original_request="Create report.pdf and upload it to Google Drive.",
        steps=[
            make_step("step_001", "file_manager", "create_file", "report.pdf"),
            make_step("step_002", "browser", "upload_file", "Google Drive"),
        ],
    )
    validator = IntentValidator(
        FakeOllamaClient(make_result(True, "Both steps support the requested goal.", []))
    )

    result = validator.validate(plan)

    assert result.consistent is True


def test_empty_plan_is_inconsistent_without_calling_model():
    plan = make_plan()
    plan.steps = []
    client = FakeOllamaClient("must not be called")

    result = IntentValidator(client).validate(plan)

    assert result.consistent is False
    assert "no steps capable" in result.reason
    assert client.prompts == []


def test_structurally_incomplete_step_is_rejected_before_model_call():
    plan = make_plan(make_step("step_001", "", "create_file", "rest.pdf"))

    with pytest.raises(ValueError, match="no agent"):
        IntentValidator(FakeOllamaClient("must not be called")).validate(plan)


def test_malformed_model_json_is_controlled_error():
    plan = make_plan(make_step("step_001", "file_manager", "create_file", "rest.pdf"))

    with pytest.raises(IntentParsingError, match="invalid JSON"):
        IntentValidator(FakeOllamaClient("{this is not valid json")).validate(plan)


def test_unknown_mismatched_step_id_is_rejected():
    plan = make_plan(make_step("step_001", "file_manager", "create_file", "rest.pdf"))
    response = make_result(False, "The plan needs review.", ["step_999"])

    with pytest.raises(ValueError, match="not present in the TaskPlan"):
        IntentValidator(FakeOllamaClient(response)).validate(plan)


def test_dangerous_operations_are_inspected_as_data_only():
    plan = TaskPlan(
        task_id="task_001",
        original_request="Review these planned actions.",
        steps=[
            make_step("step_001", "file_manager", "delete_file", "report.pdf"),
            make_step("step_002", "email", "send_email", "someone@example.com"),
            make_step("step_003", "browser", "open_url", "example.com"),
        ],
    )
    client = FakeOllamaClient(make_result(False, "The plan needs review.", []))

    result = IntentValidator(client).validate(plan)

    assert result.consistent is False
    assert "delete_file" in client.prompts[0]
    assert "send_email" in client.prompts[0]
    assert "open_url" in client.prompts[0]


def test_resource_scope_broadening_is_marked_inconsistent():
    plan = TaskPlan(
        task_id="task_001",
        original_request="Read invoice.pdf.",
        steps=[
            PlanStep(
                step_id="step_001",
                agent="file_manager",
                operation="READ",
                resource="entire Documents directory",
            )
        ],
    )
    client = FakeOllamaClient(make_result(True, "Looks consistent.", []))

    result = IntentValidator(client).validate(plan)

    assert result.consistent is False
    assert result.mismatched_steps == ["step_001"]


def test_recipient_mismatch_is_marked_inconsistent():
    plan = TaskPlan(
        task_id="task_001",
        original_request="Send this report to alice@example.com.",
        steps=[
            PlanStep(
                step_id="step_001",
                agent="email_agent",
                operation="EMAIL_SEND",
                resource="bob@example.com",
            )
        ],
    )
    client = FakeOllamaClient(make_result(True, "Looks consistent.", []))

    result = IntentValidator(client).validate(plan)

    assert result.consistent is False
    assert result.mismatched_steps == ["step_001"]


def test_structured_resource_mismatch_overrides_model_consistency():
    plan = TaskPlan(
        task_id="task_001",
        original_request="Read invoice.pdf.",
        steps=[
            PlanStep(
                step_id="step_001",
                agent="file_manager",
                operation="READ",
                resource="other.pdf",
            )
        ],
    )
    client = FakeOllamaClient(make_result(True, "Looks consistent.", []))

    result = IntentValidator(client).validate(plan)

    assert result.consistent is False
    assert result.mismatched_steps == ["step_001"]


def test_template_and_intent_operation_mismatch_overrides_model_consistency():
    plan = TaskPlan(
        task_id="task_001",
        original_request="Read invoice.pdf.",
        steps=[
            PlanStep(
                step_id="step_001",
                agent="file_manager",
                operation="DELETE",
                resource="invoice.pdf",
                template="FILE_READ",
                intent="READ",
            )
        ],
    )
    client = FakeOllamaClient(make_result(True, "Looks consistent.", []))

    result = IntentValidator(client).validate(plan)

    assert result.consistent is False
    assert result.mismatched_steps == ["step_001"]