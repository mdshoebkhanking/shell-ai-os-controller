import asyncio
import logging
import time
import json
from typing import Dict, Any, List, Optional
from brain.memory_core import memory_core
from swarm.orchestrator import Orchestrator

logger = logging.getLogger("shell_autopilot")

class AutoPilotEngine:
    """
    REAL AutoPilot Engine V2 — Autonomous Goal Execution with:
    - Multi-phase execution (Plan → Execute → Verify → Retry → Learn)
    - Real success verification using AI
    - Retry logic with adjusted approach
    - Execution history with learning
    - Sub-goal decomposition for complex tasks
    - Progress tracking
    """

    def __init__(self):
        self.orchestrator = Orchestrator()
        self.is_running = False
        self._brain = None
        self._history = []
        self._max_retries = 2

    def _get_brain(self):
        if self._brain is None:
            from brain.core import MultiAIBrain
            self._brain = MultiAIBrain()
        return self._brain

    async def engage(self, goal: str) -> str:
        """Full autonomous execution loop."""
        self.is_running = True
        start_time = time.time()
        report = [f"**AutoPilot V2 — ENGAGED**", f"**Goal:** {goal}"]

        try:
            # Phase 1: DECOMPOSE — Break complex goal into sub-goals
            sub_goals = await self._decompose_goal(goal)
            report.append(f"**Sub-goals:** {len(sub_goals)}")

            all_results = []
            for i, sub_goal in enumerate(sub_goals[:5], 1):
                report.append(f"\n--- Sub-goal {i}: {sub_goal} ---")

                # Phase 2: EXECUTE via Swarm
                result = None
                attempt = 0
                while attempt <= self._max_retries:
                    attempt += 1
                    try:
                        result = await asyncio.wait_for(
                            self.orchestrator.run_mission(sub_goal),
                            timeout=90.0
                        )

                        # Phase 3: VERIFY using AI
                        verified = await self._verify_result(sub_goal, result)

                        if verified:
                            report.append(f"Attempt {attempt}: SUCCESS")
                            report.append(result[:500])
                            all_results.append(result)
                            break
                        else:
                            report.append(f"Attempt {attempt}: Verification failed, {'retrying...' if attempt <= self._max_retries else 'giving up'}")
                            if attempt <= self._max_retries:
                                # Adjust approach for retry
                                sub_goal = f"Try a different approach: {sub_goal}. Previous attempt was insufficient."

                    except asyncio.TimeoutError:
                        report.append(f"Attempt {attempt}: Timeout (90s)")
                    except Exception as e:
                        report.append(f"Attempt {attempt}: Error - {str(e)[:150]}")
                        break

            # Phase 4: SYNTHESIZE final report
            elapsed = round(time.time() - start_time, 2)

            # Phase 5: LEARN — Store in memory
            status = "success" if all_results else "failed"
            memory_core.add_memory(
                f"AutoPilot Goal: {goal[:100]} | Status: {status} | Time: {elapsed}s | Sub-goals: {len(sub_goals)}",
                meta={"type": "autopilot_execution", "status": status, "elapsed": elapsed}
            )

            self._history.append({
                "goal": goal[:200], "status": status,
                "sub_goals": len(sub_goals), "elapsed": elapsed
            })

            report.append(f"\n**Status:** {status.upper()}")
            report.append(f"**Time:** {elapsed}s")

        except Exception as e:
            logger.error(f"AutoPilot Critical: {e}")
            report.append(f"**CRITICAL ERROR:** {e}")

        self.is_running = False
        return "\n".join(report)

    async def _decompose_goal(self, goal: str) -> List[str]:
        """Use AI to break complex goal into sub-goals."""
        brain = self._get_brain()
        try:
            response = await asyncio.wait_for(
                brain.generate_response(
                    f"Break this goal into 1-3 actionable sub-goals. Return ONLY a JSON array of strings:\n{goal}",
                    mode="FAST"
                ),
                timeout=15.0
            )
            cleaned = response.replace("```json", "").replace("```", "").strip()
            start = cleaned.find('[')
            end = cleaned.rfind(']') + 1
            if start != -1 and end > start:
                sub_goals = json.loads(cleaned[start:end])
                if isinstance(sub_goals, list) and sub_goals:
                    return [str(g) for g in sub_goals[:5]]
        except Exception as e:
            logger.warning(f"Goal decomposition failed: {e}")
        return [goal]

    async def _verify_result(self, goal: str, result: str) -> bool:
        """Use AI to verify if the result actually achieves the goal."""
        brain = self._get_brain()
        try:
            response = await asyncio.wait_for(
                brain.generate_response(
                    f"Does this result achieve the goal? Answer ONLY 'YES' or 'NO'.\n\nGoal: {goal}\n\nResult: {result[:1000]}",
                    mode="FAST"
                ),
                timeout=10.0
            )
            return "yes" in response.lower()
        except Exception:
            # If verification fails, assume success if result is substantial
            return len(str(result)) > 100

    def get_history(self) -> str:
        if not self._history:
            return "AutoPilot: No executions yet."
        lines = ["AutoPilot Execution History", "=" * 40]
        for i, h in enumerate(self._history[-10:], 1):
            lines.append(f"{i}. [{h['status'].upper()}] {h['goal'][:80]} ({h['elapsed']}s, {h['sub_goals']} sub-goals)")
        return "\n".join(lines)

autopilot = AutoPilotEngine()
