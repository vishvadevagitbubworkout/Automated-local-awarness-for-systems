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


def main() -> int:
	print("# LOCAL-FIRST AI AUTOMATION")
	user_request = input("Task:\n> ").strip()

	try:
		plan = Planner().create_plan(user_request)
	except (OllamaError, PlanParsingError, ValueError) as error:
		print(f"Planning failed: {error}")
		return 1

	print()
	print(format_plan(plan))
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
