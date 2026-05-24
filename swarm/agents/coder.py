import os
from typing import Optional

from ..base import BaseAgent, SwarmState


def _truthy(value: Optional[str]) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}

class CoderAgent(BaseAgent):
    def __init__(self, brain_core):
        super().__init__("Coder", "Developer", brain_core)

    async def execute(self, task: str, state: SwarmState) -> str:
        state.log(self.name, f"Coding Task: {task}")

        # Context from previous steps
        context = ""
        if "research_summary" in state.artifacts:
            context += f"\nResearch: {state.artifacts['research_summary']}"

        prompt = f"""
        You are an Expert Python Developer.
        TASK: {task}
        CONTEXT: {context}

        Write the complete, runnable Python code for this task.
        Wrap code in ```python blocks.
        """

        code_response = await self._generate_response(prompt, mode="CODING")

        # Simple extraction
        if "```python" in code_response:
            code = code_response.split("```python")[1].split("```")[0]
            filename = "swarm_output.py" # In future, parse filename from planner

            if not _truthy(os.getenv("SHELL_ALLOW_SWARM_FILE_WRITE")):
                state.artifacts["code_preview"] = code
                state.log(self.name, "Code generated as preview; file write blocked by policy")
                return (
                    "Code generated as preview only. File write blocked by policy. "
                    "Set SHELL_ALLOW_SWARM_FILE_WRITE=1 to allow swarm file writes."
                )

            with open(filename, "w", encoding="utf-8") as f:
                f.write(code)

            state.artifacts["code_file"] = filename
            state.log(self.name, f"Code written to {filename}")
            return f"Code generated and saved to {filename}"

        state.log(self.name, "No Python code block generated; no files written")
        return "No code block generated. No files were written."
