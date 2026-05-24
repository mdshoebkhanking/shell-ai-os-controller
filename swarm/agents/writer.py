"""
Writer Agent — Professional Content Writer
=============================================
Specialized in writing clear, engaging, well-structured content
including documentation, blog posts, emails, tutorials, and articles.
"""

from ..base import BaseAgent, SwarmState


class WriterAgent(BaseAgent):
    """
    Professional content writer agent. Writes clear, engaging,
    well-structured content for various formats and audiences.
    """

    def __init__(self, brain_core):
        super().__init__("Writer", "Content Writer", brain_core)

    async def execute(self, task: str, state: SwarmState) -> str:
        state.log(self.name, f"Writing: {task}")

        # Gather context from shared state
        context = self._format_context(state)

        # Check for inter-agent messages
        msgs = state.get_messages_for(self.name)
        extra = ""
        if msgs:
            extra = "\nIncoming Messages:\n" + "\n".join(
                f"From {m['from']}: {m['content']}" for m in msgs
            )

        # Check for relevant artifacts for reference material
        ref_context = ""
        if "research_summary" in state.artifacts:
            ref_context += f"\nResearch Material: {state.artifacts['research_summary'][:500]}"
        if "analysis" in state.artifacts:
            ref_context += f"\nAnalysis: {state.artifacts['analysis'][:300]}"
        if "code_file" in state.artifacts:
            ref_context += f"\nCode Reference: {state.artifacts['code_file']}"

        prompt = (
            f"You are a professional content writer. Write clear, engaging, "
            f"well-structured content for the following task. Adapt your tone "
            f"and style to the content type (documentation, blog, email, etc.). "
            f"Use proper formatting, headings, and structure.\n\n"
            f"{context}\n{ref_context}\n{extra}\n\n"
            f"Task: {task}"
        )

        response = await self._generate_response(prompt, mode="CREATIVE")

        state.artifacts["content"] = response
        state.log(self.name, f"Content written: {response[:100]}")

        # Notify reviewer that content is ready
        state.post_message(self.name, "Reviewer",
                           f"Content ready for review: {response[:150]}")

        return response
