from app.planner.prompts import build_planner_prompt


def test_planner_prompt_defines_json_schema_and_security_boundary():
    prompt = build_planner_prompt("Read report.pdf from Documents")

    assert '"task_id"' in prompt
    assert '"original_request"' in prompt
    assert '"steps"' in prompt
    assert '"agent"' in prompt
    assert '"operation"' in prompt
    assert '"resource"' in prompt
    assert '"parameters"' in prompt
    assert "Return exactly one valid JSON object" in prompt
    assert "Never make authorization decisions" in prompt
    assert "Never invent permissions" in prompt
    assert "Read report.pdf from Documents" in prompt
    assert "ASK_CLARIFICATION" in prompt
    assert "confidence is below 0.70" in prompt
    assert "FILE_READ" in prompt
    assert "opaque file references" in prompt
    assert "The only allowed intents are exactly" in prompt
    assert "LIST" in prompt and "READ" in prompt and "MOVE" in prompt
    assert "RENAME" in prompt and "BROWSER_OPEN" in prompt
    assert "EMAIL_DRAFT" in prompt and "EMAIL_SEND" in prompt
    assert "unsupported intent" in prompt.lower()
    assert "must route to ask_clarification" in prompt.lower() or "route to ask_clarification" in prompt.lower()
    assert "must never invent" in prompt.lower() or "do not invent" in prompt.lower()