"""
Analyst Agent — Data Analysis Expert
=======================================
Specialized in data analysis, pattern recognition, insights,
trend identification, statistical reasoning, and report generation.
"""

from ..base import BaseAgent, SwarmState


class AnalystAgent(BaseAgent):
    """
    Data analysis expert agent. Analyzes data, identifies patterns,
    provides insights and recommendations with statistical reasoning.
    """

    def __init__(self, brain_core):
        super().__init__("Analyst", "Data Analysis Expert", brain_core)

    async def execute(self, task: str, state: SwarmState) -> str:
        state.log(self.name, f"Analyzing: {task}")

        # Gather context from shared state
        context = self._format_context(state)

        # Check for inter-agent messages
        msgs = state.get_messages_for(self.name)
        extra = ""
        if msgs:
            extra = "\nIncoming Messages:\n" + "\n".join(
                f"From {m['from']}: {m['content']}" for m in msgs
            )

        # Check for relevant artifacts from other agents
        data_context = ""
        if "research_summary" in state.artifacts:
            data_context += f"\nResearch Data: {state.artifacts['research_summary'][:500]}"
        if "code_file" in state.artifacts:
            data_context += f"\nCode Output: {state.artifacts['code_file']}"

        prompt = (
            f"You are a data analyst expert. Analyze the following task thoroughly. "
            f"Provide clear insights, identify patterns, highlight trends, and give "
            f"actionable recommendations. Use structured formatting with sections.\n\n"
            f"{context}\n{data_context}\n{extra}\n\n"
            f"Task: {task}"
        )

        response = await self._generate_response(prompt, mode="REASONING")

        state.artifacts["analysis"] = response
        state.log(self.name, f"Analysis complete: {response[:100]}")

        # Notify other agents if findings are significant
        if len(response) > 200:
            state.post_message(self.name, "Planner",
                               f"Analysis findings: {response[:200]}")

        return response
