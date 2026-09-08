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