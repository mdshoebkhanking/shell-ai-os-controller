from ..base import BaseAgent, SwarmState
from shell_google_search import google_search

class ResearcherAgent(BaseAgent):
    def __init__(self, brain_core):
        super().__init__("Researcher", "Analyst", brain_core)

    async def execute(self, task: str, state: SwarmState) -> str:
        state.log(self.name, f"Researching: {task}")

        # 1. Search Query Generation
        query = await self._generate_response(
            f"Convert this research task into a Google Search Query: {task}",
            mode="FAST"
        )
        query = query.strip('"')

        # 2. Perform Search
        search_results = await google_search(query)

        # 3. Summarize
        summary_prompt = f"""
        Analyze these search results for the task: "{task}"

        RESULTS:
        {search_results}

        Provide a concise technical summary.
        """
        summary = await self._generate_response(summary_prompt, mode="SMART")

        state.artifacts["research_summary"] = summary
        state.log(self.name, "Research Completed.")
        return summary
