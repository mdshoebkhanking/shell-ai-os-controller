"""
Swarm Orchestrator V3 — ULTRA Mission Control
================================================
Enhanced routing with 8 agent types, parallel execution,
dynamic agent creation, inter-agent messaging, detailed stats.
"""

import asyncio
import uuid
import time
import logging
from typing import Dict, List, Optional
from collections import Counter
from brain.core import MultiAIBrain
from .base import SwarmState, BaseAgent
from .agents.planner import PlannerAgent
from .agents.researcher import ResearcherAgent
from .agents.coder import CoderAgent

logger = logging.getLogger("swarm_orchestrator")


class Orchestrator:
    """
    The Queen Bee V3 — Manages swarm missions with:
    - 8 specialized agent types
    - Intelligent multi-keyword routing
    - Parallel step execution
    - Dynamic custom agent creation
    - Inter-agent messaging
    - Better error recovery (retry + skip + alternative)
    - Mission history tracking with detailed stats
    - Step-level timeout management
    """

    ROUTING_KEYWORDS = {
        "researcher": [
            "research", "search", "find", "analyze", "investigate",
            "look up", "discover", "explore", "learn about", "information",
            "what is", "how does", "explain", "summarize", "compare",
            "news", "trend", "data about", "statistics",
        ],
        "coder": [
            "code", "write code", "script", "create", "build", "implement",
            "function", "class", "module", "program", "develop",
            "html", "css", "python", "javascript", "api", "database",
            "refactor", "deploy", "generate", "architect",
        ],
        "analyst": [
            "data", "analyze", "insight", "pattern", "statistics",
            "report", "trend", "metric", "dashboard", "correlation",
            "distribution", "aggregate", "breakdown", "forecast",
        ],
        "debugger": [
            "bug", "fix", "error", "crash", "debug", "traceback",
            "exception", "broken", "failing", "issue", "stacktrace",
            "undefined", "null", "segfault", "memory leak",
        ],
        "optimizer": [
            "optimize", "performance", "speed", "fast", "slow",
            "efficient", "cache", "memory usage", "reduce", "improve",
            "bottleneck", "latency", "throughput", "benchmark",
        ],
        "writer": [
            "write", "document", "blog", "readme", "article",
            "content", "essay", "copy", "draft", "story",
            "email", "message", "letter", "tutorial", "guide",
        ],
        "reviewer": [
            "review", "check", "verify", "audit", "quality",
            "approve", "feedback", "evaluate", "assess", "inspect",
            "critique", "validate", "proofread", "test",
        ],
    }

    def __init__(self):
        self.brain = MultiAIBrain()
        self.agents: Dict[str, BaseAgent] = {}
        self._mission_history: List[Dict] = []
        self._register_agents()

    def _register_agents(self):
        """Register all 8 specialized agents."""
        self.agents["planner"] = PlannerAgent(self.brain)
        self.agents["researcher"] = ResearcherAgent(self.brain)
        self.agents["coder"] = CoderAgent(self.brain)

        # Import and register new agents
        from .agents.analyst import AnalystAgent
        from .agents.debugger import DebuggerAgent
        from .agents.optimizer import OptimizerAgent
        from .agents.writer import WriterAgent
        from .agents.reviewer import ReviewerAgent

        self.agents["analyst"] = AnalystAgent(self.brain)
        self.agents["debugger"] = DebuggerAgent(self.brain)
        self.agents["optimizer"] = OptimizerAgent(self.brain)
        self.agents["writer"] = WriterAgent(self.brain)
        self.agents["reviewer"] = ReviewerAgent(self.brain)

    def _route_step(self, step: str) -> str:
        """Intelligent step routing with multi-keyword matching across 8 agent types."""
        step_lower = step.lower()
        if any(
            phrase in step_lower
            for phrase in (
                "do not create",
                "do not write",
                "do not modify",
                "no file",
                "without creating",
                "readiness report",
                "smoke test",
            )
        ):
            return "reviewer"

        scores: Dict[str, int] = {}
        for agent_key, keywords in self.ROUTING_KEYWORDS.items():
            scores[agent_key] = sum(1 for kw in keywords if kw in step_lower)

        best_agent = max(scores, key=scores.get)
        if scores[best_agent] > 0:
            return best_agent

        # Default to a read-only reviewer path. Code generation is selected
        # only when the step explicitly looks like a coding task.
        return "reviewer"

    # ══════════════════════════════════════════════════════════════
    # PARALLEL STEP EXECUTION
    # ══════════════════════════════════════════════════════════════

    async def _execute_parallel_steps(self, steps: List[str],
                                       state: SwarmState) -> List[str]:
        """Execute independent steps in parallel for faster mission completion."""
        tasks = []
        agents_used = []
        for step in steps:
            agent_key = self._route_step(step)
            agent = self.agents.get(agent_key, self.agents["coder"])
            agents_used.append(agent_key)
            tasks.append(
                asyncio.wait_for(agent.execute(step, state), timeout=60.0)
            )
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [
            str(r)[:500] if not isinstance(r, Exception) else f"Error: {r}"
            for r in results
        ]

    # ══════════════════════════════════════════════════════════════
    # DYNAMIC AGENT CREATION
    # ══════════════════════════════════════════════════════════════

    def create_custom_agent(self, name: str, role: str, system_prompt: str) -> str:
        """Create a one-off agent with a custom system prompt at runtime."""
        brain_ref = self.brain
        prompt_ref = system_prompt

        class CustomAgent(BaseAgent):
            async def execute(self, task, state):
                context = self._format_context(state)
                msgs = state.get_messages_for(self.name)
                extra = "\n".join(f"Message from {m['from']}: {m['content']}" for m in msgs)
                response = await self._generate_response(
                    f"{prompt_ref}\n\nContext:\n{context}\n{extra}\n\nTask: {task}",
                    mode="SMART"
                )
                state.artifacts[f"custom_{name}"] = response
                state.log(self.name, f"Custom agent complete: {response[:100]}")
                return response

        self.agents[name] = CustomAgent(name, role, self.brain)
        return f"Agent '{name}' created with role: {role}"

    # ══════════════════════════════════════════════════════════════
    # MAIN MISSION EXECUTION
    # ══════════════════════════════════════════════════════════════

    async def run_mission(self, user_request: str,
                          parallel: bool = False) -> str:
        """Execute a full mission with enhanced routing, parallel execution, and error handling."""
        mission_id = f"mission_{uuid.uuid4().hex[:8]}"
        state = SwarmState(task_id=mission_id, original_request=user_request)
        state.log("Orchestrator", f"Mission Started: {user_request}")
        start_time = time.time()
        agents_used = []

        try:
            # ═══ PHASE 1: PLANNING (45s timeout) ═══
            state.log("Orchestrator", "Activating Planner Agent...")
            try:
                await asyncio.wait_for(
                    self.agents["planner"].execute(user_request, state),
                    timeout=45.0
                )
                agents_used.append("planner")
            except asyncio.TimeoutError:
                state.log("Orchestrator", "Planner timed out, using single-step plan")
                state.plan = [user_request]
            except Exception as e:
                state.log("Orchestrator", f"Planner error: {str(e)[:100]}")
                state.plan = [user_request]

            if not state.plan:
                state.plan = [user_request]

            output_report = (
                f"**Swarm Mission Report V3**\n"
                f"**Mission ID:** {mission_id}\n"
                f"**Request:** {user_request}\n"
                f"**Plan:** {len(state.plan)} steps\n"
                f"**Mode:** {'Parallel' if parallel else 'Sequential'}\n"
            )

            # ═══ PHASE 2: EXECUTION ═══
            completed_steps = 0
            failed_steps = 0
            steps_to_execute = state.plan[:7]  # Max 7 steps

            if parallel and len(steps_to_execute) > 1:
                # Parallel execution mode
                state.log("Orchestrator", f"Executing {len(steps_to_execute)} steps in parallel")
                parallel_results = await self._execute_parallel_steps(
                    steps_to_execute, state
                )
                for idx, result in enumerate(parallel_results):
                    step = steps_to_execute[idx]
                    agent_key = self._route_step(step)
                    agents_used.append(agent_key)
                    output_report += f"\n**[Step {idx+1}: {step[:80]}]**\n"
                    output_report += f"**Agent:** {self.agents.get(agent_key, self.agents['coder']).name}\n"
                    if result.startswith("Error:"):
                        output_report += f"**Error:** {result}\n"
                        failed_steps += 1
                    else:
                        output_report += f"**Result:** {result[:300]}\n"
                        completed_steps += 1
            else:
                # Sequential execution mode
                for idx, step in enumerate(steps_to_execute):
                    # Check total mission timeout (180s)
                    if time.time() - start_time > 180:
                        output_report += f"\n**[Step {idx+1}]** Skipped — Mission timeout (180s)\n"
                        break

                    agent_key = self._route_step(step)
                    selected_agent = self.agents.get(agent_key, self.agents["coder"])
                    agents_used.append(agent_key)

                    state.log("Orchestrator", f"Step {idx+1}: '{step[:50]}' -> {selected_agent.name}")
                    output_report += f"\n**[Step {idx+1}: {step[:80]}]**\n"
                    output_report += f"**Agent:** {selected_agent.name}\n"

                    # Try execution with retry
                    success = False
                    for attempt in range(2):  # Max 2 attempts per step
                        try:
                            result = await asyncio.wait_for(
                                selected_agent.execute(step, state),
                                timeout=60.0
                            )
                            output_report += f"**Result:** {result[:300]}\n"
                            completed_steps += 1
                            success = True
                            break

                        except asyncio.TimeoutError:
                            if attempt == 0:
                                output_report += f"**Attempt {attempt+1}:** Timeout, retrying...\n"
                            else:
                                output_report += f"**Timeout** — Step skipped\n"

                        except Exception as e:
                            error_str = str(e)
                            # Hard stop on quota errors
                            if "429" in error_str or "quota" in error_str.lower():
                                output_report += f"**API Quota Exceeded** — Mission paused\n"
                                break
                            if attempt == 0:
                                output_report += f"**Attempt {attempt+1}:** Error, retrying...\n"
                            else:
                                output_report += f"**Error:** {error_str[:150]}\n"

                    if not success:
                        failed_steps += 1

            # ═══ PHASE 3: REPORT ═══
            elapsed = round(time.time() - start_time, 2)
            state.status = "completed"

            # Check for inter-agent messages
            msg_count = len(state.get_all_messages())
            msg_line = f"Inter-Agent Messages: {msg_count}\n" if msg_count > 0 else ""

            output_report += (
                f"\n{'='*40}\n"
                f"**Mission Complete**\n"
                f"Steps: {completed_steps} completed, {failed_steps} failed\n"
                f"Agents Used: {', '.join(set(agents_used))}\n"
                f"{msg_line}"
                f"Time: {elapsed}s\n"
            )

            # Save to history
            self._mission_history.append({
                "id": mission_id,
                "request": user_request[:200],
                "steps_total": len(steps_to_execute),
                "steps_completed": completed_steps,
                "steps_failed": failed_steps,
                "elapsed": elapsed,
                "status": "success" if failed_steps == 0 else "partial",
                "agents_used": list(set(agents_used)),
                "parallel": parallel,
            })

            return output_report

        except Exception as e:
            return (
                f"**Swarm Critical Error:** {str(e)}\n"
                f"Request: {user_request}"
            )

    # ══════════════════════════════════════════════════════════════
    # HISTORY & STATS
    # ══════════════════════════════════════════════════════════════

    def get_mission_history(self) -> str:
        """Get mission execution history."""
        if not self._mission_history:
            return "No missions executed yet."
        lines = ["Swarm Mission History", "=" * 50]
        for m in self._mission_history[-10:]:
            mode = "PAR" if m.get("parallel") else "SEQ"
            lines.append(
                f"  [{m['status'].upper():7s}] {m['id']} | "
                f"{m['steps_completed']}/{m['steps_total']} steps ({mode}) | "
                f"{m['elapsed']}s | {m['request'][:60]}"
            )
        return "\n".join(lines)

    def get_stats(self) -> Dict:
        """Get orchestrator statistics (basic)."""
        total = len(self._mission_history)
        if total == 0:
            return {"total_missions": 0}
        return {
            "total_missions": total,
            "success_rate": sum(1 for m in self._mission_history if m["status"] == "success") / total,
            "avg_time": sum(m["elapsed"] for m in self._mission_history) / total,
            "total_steps": sum(m["steps_total"] for m in self._mission_history),
        }

    def get_detailed_stats(self) -> Dict:
        """Get detailed orchestrator statistics with agent usage breakdown."""
        total = len(self._mission_history)
        if total == 0:
            return {"total_missions": 0}

        agent_usage: Counter = Counter()
        for m in self._mission_history:
            for agent in m.get("agents_used", []):
                agent_usage[agent] += 1

        parallel_count = sum(1 for m in self._mission_history if m.get("parallel"))

        return {
            "total_missions": total,
            "success_rate": round(
                sum(1 for m in self._mission_history if m["status"] == "success") / total, 3
            ),
            "avg_time": round(
                sum(m["elapsed"] for m in self._mission_history) / total, 2
            ),
            "total_steps": sum(m["steps_total"] for m in self._mission_history),
            "total_steps_completed": sum(m["steps_completed"] for m in self._mission_history),
            "total_steps_failed": sum(m["steps_failed"] for m in self._mission_history),
            "parallel_missions": parallel_count,
            "sequential_missions": total - parallel_count,
            "agent_usage": dict(agent_usage),
            "available_agents": list(self.agents.keys()),
        }
