from ..base import BaseAgent, SwarmState
import json

class PlannerAgent(BaseAgent):
    def __init__(self, brain_core):
        super().__init__("Planner", "Architect", brain_core)

    async def execute(self, task: str, state: SwarmState) -> str:
        prompt = f"""
        You are the Architecture Planner of the Hive Mind.
        CONTEXT: {self._format_context(state)}

        TASK: {task}

        Create a step-by-step execution plan.
        RULES:
        1. Return ONLY a JSON list of strings.
        2. No introductory text. No markdown formatting.
        3. Example: ["Research library X", "Write script.py", "Test script.py"]
        """

        response = await self._generate_response(prompt, mode="SMART")

        # Robust Parsing
        try:
            cleaned = response.replace("```json", "").replace("```", "").strip()
            start = cleaned.find('[')
            end = cleaned.rfind(']') + 1

            if start != -1 and end != -1:
                plan_str = cleaned[start:end]
                state.plan = json.loads(plan_str)
                state.log(self.name, f"Plan Created: {state.plan}")
                return "Plan successfully created."
            else:
                state.log(self.name, f"Failed to find JSON brackets in: {cleaned[:100]}...")
                # Fallback: Create a single-step plan from the raw text
                state.plan = [f"Analyze and Execute: {task}"]
                return "Plan fallback triggered."
        except json.JSONDecodeError as e:
            state.log(self.name, f"JSON Error: {e}")
            state.plan = [f"Execute: {task}"] # Emergency Fallback
            return "JSON Error, switched to direct execution."
        except Exception as e:
            return f"Planning Error: {e}"
