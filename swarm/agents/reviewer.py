"""
Reviewer Agent — Code & Content Review Expert
================================================
Specialized in reviewing code and content for quality,
providing constructive feedback, identifying issues,
and suggesting improvements.
"""

from ..base import BaseAgent, SwarmState


class ReviewerAgent(BaseAgent):
    """
    Code and content review expert agent. Provides constructive feedback,
    identifies issues, evaluates quality, and suggests improvements.
    """

    def __init__(self, brain_core):
        super().__init__("Reviewer", "Quality Reviewer", brain_core)

    async def execute(self, task: str, state: SwarmState) -> str:
        state.log(self.name, f"Reviewing: {task}")

        # Gather context from shared state
        context = self._format_context(state)

        # Check for inter-agent messages
        msgs = state.get_messages_for(self.name)
        extra = ""
        if msgs:
            extra = "\nIncoming Messages:\n" + "\n".join(
                f"From {m['from']}: {m['content']}" for m in msgs
            )

        # Check for all artifacts to review
        review_context = ""
        reviewable_keys = ["code_file", "content", "analysis", "optimization",
                           "debug_report", "research_summary"]
        for key in reviewable_keys:
            if key in state.artifacts:
                value = state.artifacts[key]
                review_context += f"\n{key}: {str(value)[:400]}"

        prompt = (
            f"You are a thorough code and content reviewer. Review the following "
            f"task and any associated artifacts. Provide:\n"
            f"1. Quality assessment (1-10 score with justification)\n"
            f"2. Issues found (bugs, errors, unclear sections)\n"
            f"3. Specific improvement suggestions\n"
            f"4. What was done well (positive feedback)\n"
            f"5. Final recommendation (approve / needs changes / reject)\n\n"
            f"{context}\n{review_context}\n{extra}\n\n"
            f"Task: {task}"
        )

        response = await self._generate_response(prompt, mode="REASONING")

        state.artifacts["review"] = response
        state.log(self.name, f"Review complete: {response[:100]}")

        # Notify relevant agents about review results
        if "needs changes" in response.lower() or "reject" in response.lower():
            if "code_file" in state.artifacts:
                state.post_message(self.name, "Coder",
                                   f"Review feedback: {response[:200]}")
            if "content" in state.artifacts:
                state.post_message(self.name, "Writer",
                                   f"Review feedback: {response[:200]}")

        return response
