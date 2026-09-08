from app.planner.ollama_client import OllamaClient
from app.planner.parsing import parse_task_plan
from app.planner.prompts import build_planner_prompt
from app.planner.schemas import TaskPlan


class Planner:
	"""Coordinate local model planning without executing the resulting plan."""

	def __init__(self, ollama_client: OllamaClient | None = None):
		self.ollama_client = ollama_client or OllamaClient()

	def create_plan(self, user_request: str) -> TaskPlan:
		if not isinstance(user_request, str) or not user_request.strip():
			raise ValueError("The user request must not be empty.")

		prompt = build_planner_prompt(user_request)
		raw_response = self.ollama_client.generate(prompt)
		return parse_task_plan(raw_response)
