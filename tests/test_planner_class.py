import json

import pytest

from app.planner.planner import Planner
from app.planner.schemas import TaskPlan


class FakeOllamaClient:
    def __init__(self, response):
        self.response = response
        self.prompts = []

    def generate(self, prompt):
        self.prompts.append(prompt)
        return self.response


def test_planner_coordinates_prompt_model_and_validation():
    response = json.dumps(
        {
            "task_id": "task_001",
            "original_request": "Read report.pdf from Documents",
            "steps": [
                {
                    "step_id": "step_001",
                    "agent": "file_agent",
                    "operation": "READ",
                    "resource": "report.pdf",
                    "parameters": {"location": "Documents"},
                }
            ],
        }
    )
    client = FakeOllamaClient(response)

    plan = Planner(client).create_plan("Read report.pdf from Documents")

    assert isinstance(plan, TaskPlan)
    assert plan.steps[0].agent == "file_agent"
    assert len(client.prompts) == 1
    assert "Read report.pdf from Documents" in client.prompts[0]


def test_planner_rejects_empty_user_request():
    with pytest.raises(ValueError, match="must not be empty"):
        Planner(FakeOllamaClient("unused")).create_plan("  ")


def make_planner(response):
    return Planner(FakeOllamaClient(json.dumps(response)))


def test_planner_identifies_simple_file_task():
    planner = make_planner(
        {
            "task_id": "task_001",
            "original_request": "Read report.pdf from Documents.",
            "steps": [
                {
                    "step_id": "step_001",
                    "agent": "file_agent",
                    "operation": "READ",
                    "resource": "report.pdf",
                    "parameters": {"location": "Documents"},
                }
            ],
        }
    )

    plan = planner.create_plan("Read report.pdf from Documents.")

    assert plan.steps[0].agent == "file_agent"
    assert plan.steps[0].operation == "READ"


def test_planner_identifies_multiple_logical_actions():
    planner = make_planner(
        {
            "task_id": "task_001",
            "original_request": "Read report.pdf and summarize it.",
            "steps": [
                {
                    "step_id": "step_001",
                    "agent": "file_agent",
                    "operation": "READ",
                    "resource": "report.pdf",
                    "parameters": {},
                },
                {
                    "step_id": "step_002",
                    "agent": "summarization_agent",
                    "operation": "SUMMARIZE",
                    "resource": "report.pdf",
                    "parameters": {},
                },
            ],
        }
    )

    plan = planner.create_plan("Read report.pdf and summarize it.")

    assert len(plan.steps) == 2
    assert [step.operation for step in plan.steps] == ["READ", "SUMMARIZE"]


def test_planner_identifies_browser_task():
    planner = make_planner(
        {
            "task_id": "task_001",
            "original_request": "Open the university website and search for exam results.",
            "steps": [
                {
                    "step_id": "step_001",
                    "agent": "browser_agent",
                    "operation": "OPEN",
                    "resource": "university website",
                    "parameters": {},
                },
                {
                    "step_id": "step_002",
                    "agent": "browser_agent",
                    "operation": "SEARCH",
                    "resource": "exam results",
                    "parameters": {},
                },
            ],
        }
    )

    plan = planner.create_plan(
        "Open the university website and search for exam results."
    )

    assert all(step.agent == "browser_agent" for step in plan.steps)
    assert [step.operation for step in plan.steps] == ["OPEN", "SEARCH"]


def test_planner_identifies_email_task():
    planner = make_planner(
        {
            "task_id": "task_001",
            "original_request": "Send an email saying the meeting is postponed.",
            "steps": [
                {
                    "step_id": "step_001",
                    "agent": "email_agent",
                    "operation": "SEND",
                    "resource": "email",
                    "parameters": {"body": "The meeting is postponed."},
                }
            ],
        }
    )

    plan = planner.create_plan("Send an email saying the meeting is postponed.")

    assert plan.steps[0].agent == "email_agent"
    assert plan.steps[0].operation == "SEND"


def test_planner_rejects_malformed_model_output():
    planner = Planner(FakeOllamaClient("not valid JSON"))

    with pytest.raises(ValueError, match="invalid JSON"):
        planner.create_plan("Read report.pdf")


def test_planner_describes_deletion_without_executing_it(tmp_path):
    target = tmp_path / "important.txt"
    planner = make_planner(
        {
            "task_id": "task_001",
            "original_request": "Delete all files in my Documents folder.",
            "steps": [
                {
                    "step_id": "step_001",
                    "agent": "file_agent",
                    "operation": "DELETE",
                    "resource": "Documents",
                    "parameters": {"recursive": True},
                }
            ],
        }
    )

    plan = planner.create_plan("Delete all files in my Documents folder.")

    assert plan.steps[0].operation == "DELETE"
    assert not target.exists()