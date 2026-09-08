from app.intent.parsing import IntentParsingError
from app.intent.schemas import IntentCheckResult
from app.intent.validator import IntentValidator
from app.planner.ollama_client import OllamaError
from app.planner.planner import Planner
from app.planner.parsing import PlanParsingError
from app.planner.schemas import TaskPlan


def format_plan(plan: TaskPlan) -> str:
	lines = [
		"Generated Plan:",
		"",
		f"Task ID: {plan.task_id}",
		"",
	]

	for index, step in enumerate(plan.steps, start=1):
		lines.extend(
			[
				f"Step {index}",
				f"Agent: {step.agent}",
				f"Operation: {step.operation}",
				f"Resource: {step.resource}",
				"Parameters:",
			]
		)
		if step.parameters:
			lines.extend(
				f"{key}: {value}" for key, value in step.parameters.items()
			)
		else:
			lines.append("{}")
		lines.append("")

	return "\n".join(lines).rstrip()


def format_intent_result(result: IntentCheckResult) -> str:
	status = "CONSISTENT" if result.consistent else "INCONSISTENT"
	lines = [
		"Intent Validation:",
		"",
		f"Status: {status}",
		"",
		"Reason:",
		result.reason,
	]
	if result.mismatched_steps:
		lines.extend(["", "Mismatched Steps:", *result.mismatched_steps])
	return "\n".join(lines)


def main() -> int:
	print("# LOCAL-FIRST AI AUTOMATION")
	user_request = input("Task:\n> ").strip()

	try:
		plan = Planner().create_plan(user_request)
		intent_result = IntentValidator().validate(plan)
	except (OllamaError, PlanParsingError, IntentParsingError, ValueError) as error:
		print(f"Planning failed: {error}")
		return 1

	print()
	print(format_plan(plan))
	print()
	print(format_intent_result(intent_result))
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
