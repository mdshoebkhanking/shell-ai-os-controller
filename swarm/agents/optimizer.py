"""
Optimizer Agent — Performance Optimization Expert
====================================================
Specialized in analyzing code and systems for bottlenecks,
suggesting performance improvements, caching strategies,
and resource usage reduction.
"""

from ..base import BaseAgent, SwarmState


class OptimizerAgent(BaseAgent):
    """
    Performance optimization expert agent. Analyzes code and systems
    for bottlenecks, suggests improvements, caching, and efficiency gains.
    """

    def __init__(self, brain_core):
        super().__init__("Optimizer", "Performance Expert", brain_core)

    async def execute(self, task: str, state: SwarmState) -> str:
        state.log(self.name, f"Optimizing: {task}")

        # Gather context from shared state
        context = self._format_context(state)

        # Check for inter-agent messages
        msgs = state.get_messages_for(self.name)
        extra = ""
        if msgs:
            extra = "\nIncoming Messages:\n" + "\n".join(
                f"From {m['from']}: {m['content']}" for m in msgs
            )

        # Check for relevant artifacts
        perf_context = ""
        if "code_file" in state.artifacts:
            perf_context += f"\nCode File: {state.artifacts['code_file']}"
        if "debug_report" in state.artifacts:
            perf_context += f"\nDebug Report: {state.artifacts['debug_report'][:300]}"
        if "analysis" in state.artifacts:
            perf_context += f"\nAnalysis: {state.artifacts['analysis'][:300]}"

        prompt = (
            f"You are a performance optimization expert. Analyze the code or system "
            f"described below for performance bottlenecks. Provide:\n"
            f"1. Identified bottlenecks\n"
            f"2. Optimized code or configuration (in ```python blocks)\n"
            f"3. Expected performance improvements\n"
            f"4. Caching and memory optimization strategies\n"
            f"5. Benchmarking suggestions\n\n"
            f"{context}\n{perf_context}\n{extra}\n\n"
            f"Task: {task}"
        )

        response = await self._generate_response(prompt, mode="CODING")

        state.artifacts["optimization"] = response
        state.log(self.name, f"Optimization complete: {response[:100]}")

        return response
