"""
Debugger Agent — Bug Finding & Fixing Expert
===============================================
Specialized in identifying bugs, explaining root causes,
analyzing tracebacks, and suggesting fixes with corrected code.
"""

from ..base import BaseAgent, SwarmState


class DebuggerAgent(BaseAgent):
    """
    Debugging expert agent. Finds bugs, explains root causes,
    analyzes error traces, and provides corrected code.
    """

    def __init__(self, brain_core):
        super().__init__("Debugger", "Bug Fixing Expert", brain_core)

    async def execute(self, task: str, state: SwarmState) -> str:
        state.log(self.name, f"Debugging: {task}")

        # Gather context from shared state
        context = self._format_context(state)

        # Check for inter-agent messages
        msgs = state.get_messages_for(self.name)
        extra = ""
        if msgs:
            extra = "\nIncoming Messages:\n" + "\n".join(
                f"From {m['from']}: {m['content']}" for m in msgs
            )

        # Check for code artifacts from other agents
        code_context = ""
        if "code_file" in state.artifacts:
            code_context += f"\nCode File: {state.artifacts['code_file']}"
        if "analysis" in state.artifacts:
            code_context += f"\nAnalysis: {state.artifacts['analysis'][:300]}"

        prompt = (
            f"You are a debugging expert. Find bugs in the code or system described below. "
            f"Explain the root cause clearly, show the problematic code, and provide "
            f"corrected code with explanations. Include:\n"
            f"1. Bug identification\n"
            f"2. Root cause analysis\n"
            f"3. Corrected code (in ```python blocks)\n"
            f"4. Prevention tips\n\n"
            f"{context}\n{code_context}\n{extra}\n\n"
            f"Task: {task}"
        )

        response = await self._generate_response(prompt, mode="CODING")

        state.artifacts["debug_report"] = response
        state.log(self.name, f"Debug report complete: {response[:100]}")

        # Notify coder if fixes are needed
        if "```" in response:
            state.post_message(self.name, "Coder",
                               f"Fix required: {response[:200]}")

        return response
