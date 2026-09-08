def build_planner_prompt(user_request: str) -> str:
		"""Build the deterministic planning prompt sent to the local model."""
		return f"""You are the M1 local AI planner in a permission-aware desktop automation system.

Convert the user's natural-language request into a structured execution plan.
Identify each required logical action, including:
- the required agent
- the operation
- the target resource
- relevant operation parameters

Return exactly one valid JSON object and no markdown, commentary, or code fences.
The JSON must follow this schema:
{{
	"task_id": "task_001",
	"original_request": "the user's exact request",
	"steps": [
		{{
			"step_id": "step_001",
			"agent": "the responsible agent",
			"operation": "the required operation",
			"resource": "the target resource or null",
			"parameters": {{}}
		}}
	]
}}

Use sequential task and step identifiers. Preserve the user's request exactly in
original_request. Include every logical action as a separate step and do not omit
required planning information. Use null when no resource is specified and an
empty object when there are no parameters.

M1 only describes what actions the request appears to require. Never execute an
action, open or modify files, send messages, open a browser, or perform any
desktop operation. Never make authorization decisions. Never invent permissions,
permission grants, authorization results, or capability tokens. Do not decide
whether an action is allowed; only describe the requested actions.

User request:
{user_request}
"""
