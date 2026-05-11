"""
HyperCortex — GOD-MODE REASONING ENGINE V5
=============================================
Multi-step reasoning with self-reflection, confidence scoring,
tool chaining, error recovery, and parallel reasoning.

Features:
- 10+ intent types with keyword scoring
- AI-powered plan generation
- Tool routing via ToolRegistry
- Memory-augmented reasoning
- 5-phase: Intent -> Memory -> Plan -> Execute -> Synthesize
- Self-reflection: reviews own answers for accuracy
- Confidence scoring: language-based certainty estimation
- Tool chaining: template substitution between steps
- Error recovery: alternative strategy generation on failure
- Parallel reasoning: dual-path analysis with best-pick
"""

import asyncio
import logging
import json
import time
from typing import List, Dict, Any, Optional
from datetime import datetime

from brain.router import SmartRouter
from brain.memory_core import memory_core

logger = logging.getLogger("HyperCortex")


class HyperCortex:
    """
    GOD-MODE REASONING ENGINE V5 — Real multi-step reasoning with:
    - 10+ intent types (WEB, CODE, SYSTEM, CREATIVE, RESEARCH, DATA, SOCIAL, SECURITY, AUTOMATION, FILE, GENERAL)
    - Multi-step plan generation using AI
    - Real tool routing via ToolRegistry
    - Memory-augmented reasoning (checks past similar queries)
    - Execution with error recovery and alternative strategies
    - Learning from results
    - Self-reflection on generated answers
    - Confidence scoring via language analysis
    - Tool chaining with template substitution
    - Parallel dual-path reasoning
    """

    INTENT_KEYWORDS = {
        "WEB": [
            "search", "find", "google", "look up", "website", "url",
            "browse", "news", "prices", "online", "download",
        ],
        "CODE": [
            "code", "script", "function", "class", "debug", "fix bug",
            "program", "python", "javascript", "html", "api", "sql",
            "compile", "run code", "repository", "git",
        ],
        "SYSTEM": [
            "system", "pc", "cpu", "ram", "disk", "process", "kill",
            "install", "uninstall", "restart", "shutdown", "service",
            "registry", "driver", "update",
        ],
        "CREATIVE": [
            "write story", "poem", "creative", "imagine", "design",
            "compose", "lyrics", "novel", "blog post", "essay", "content",
            "fiction", "narrative", "brainstorm",
        ],
        "RESEARCH": [
            "research", "analyze", "analysis", "compare", "pros and cons",
            "deep dive", "report", "case study", "investigate",
            "comprehensive", "literature review",
        ],
        "DATA": [
            "data", "csv", "excel", "json", "database", "statistics",
            "chart", "graph", "analyze data", "parse", "dataset",
            "visualization", "pandas", "spreadsheet",
        ],
        "SOCIAL": [
            "whatsapp", "instagram", "telegram", "email", "message",
            "send", "post", "tweet", "social", "notification", "chat",
        ],
        "SECURITY": [
            "security", "scan", "vulnerability", "hack", "threat",
            "malware", "encrypt", "password", "audit", "firewall",
            "antivirus", "permission",
        ],
        "AUTOMATION": [
            "automate", "workflow", "schedule", "cron", "repeat",
            "batch", "macro", "bot", "pipeline", "trigger",
        ],
        "FILE": [
            "file", "folder", "rename", "move", "copy", "delete",
            "organize", "zip", "extract", "convert", "directory",
            "path", "backup",
        ],
    }

    HEDGE_WORDS = {
        "maybe", "perhaps", "i think", "might", "could be",
        "possibly", "not sure", "uncertain", "approximately", "roughly",
    }

    DEFINITIVE_WORDS = {
        "is", "will", "certainly", "definitely", "always",
        "exactly", "precisely", "confirmed", "proven", "absolutely",
    }

    def __init__(self):
        self.memory = memory_core
        self.thought_depth = 5
        self._brain = None
        self._execution_history = []

    def _get_brain(self):
        if self._brain is None:
            from brain.core import MultiAIBrain
            self._brain = MultiAIBrain()
        return self._brain

    # ══════════════════════════════════════════════════════════════
    # MAIN ENTRY POINT
    # ══════════════════════════════════════════════════════════════

    async def omni_think(self, user_query: str, use_reflection: bool = True,
                         use_parallel: bool = False) -> Any:
        """
        Main entry point for God-Mode execution.

        Returns a structured dict with answer, trace, confidence, intent, elapsed,
        and steps_executed. For backward compatibility, str() on the result gives
        just the answer text.
        """
        start = time.time()
        reasoning_trace = []
        logger.info(f"HyperCortex V5 Activated: {user_query[:120]}")

        # ── Phase 1: Classify intent ──
        intent = self._classify_intent(user_query)
        reasoning_trace.append(f"Intent classified: {intent}")
        logger.info(f"Intent Classified: {intent}")

        # ── Phase 2: Check memory for similar past queries ──
        past = self.memory.search_memory(user_query, top_k=2)
        context = ""
        if past:
            context = "\n".join([m.get("text", "")[:200] for m in past])
            reasoning_trace.append(f"Found {len(past)} related memories")

        # ── Phase 3: Generate plan using AI ──
        plan = await self._ai_plan(user_query, intent, context)
        reasoning_trace.append(f"Plan generated: {len(plan)} steps")
        logger.info(f"Plan generated with {len(plan)} steps")

        # ── Phase 4: Execute plan steps (with chaining + recovery) ──
        results = await self._execute_plan_with_chaining(plan[:self.thought_depth], user_query)
        reasoning_trace.append(f"Executed {len(results)} steps")

        # ── Phase 5: Synthesize final answer ──
        combined = "\n".join(str(r) for r in results)
        final_answer = await self._synthesize(user_query, combined)
        reasoning_trace.append("Synthesis complete")

        # ── Phase 5b: Optional parallel reasoning ──
        if use_parallel:
            parallel_result = await self._parallel_reason(user_query)
            if parallel_result["confidence"] > self._estimate_confidence(final_answer, user_query):
                final_answer = parallel_result["answer"]
                reasoning_trace.append(f"Parallel reasoning upgraded answer (conf={parallel_result['confidence']})")

        # ── Phase 6: Self-reflection ──
        if use_reflection:
            final_answer = await self._self_reflect(user_query, final_answer)
            reasoning_trace.append("Self-reflection applied")

        # ── Phase 7: Score confidence ──
        confidence = self._estimate_confidence(final_answer, user_query)
        reasoning_trace.append(f"Confidence: {confidence}")

        # ── Phase 8: Learn from execution ──
        elapsed = round(time.time() - start, 2)
        self.memory.add_memory(
            f"Query: {user_query[:100]} | Intent: {intent} | Time: {elapsed}s | Conf: {confidence}",
            meta={"type": "hyper_cortex_execution", "intent": intent, "confidence": confidence}
        )
        self._execution_history.append({
            "query": user_query[:200],
            "intent": intent,
            "steps": len(plan),
            "elapsed": elapsed,
            "confidence": confidence,
        })

        logger.info(f"HyperCortex completed in {elapsed}s (confidence={confidence})")

        # Structured result with backward-compatible str()
        return HyperCortexResult(
            answer=final_answer,
            trace=reasoning_trace,
            confidence=confidence,
            intent=intent,
            elapsed=elapsed,
            steps_executed=len(results),
        )

    # ══════════════════════════════════════════════════════════════
    # INTENT CLASSIFICATION
    # ══════════════════════════════════════════════════════════════

    def _classify_intent(self, query: str) -> str:
        """Classify query into one of 10+ intent categories using keyword scoring."""
        q = query.lower()

        best_intent = "GENERAL"
        best_score = 0
        for intent, keywords in self.INTENT_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in q)
            if score > best_score:
                best_score = score
                best_intent = intent
        return best_intent

    # ══════════════════════════════════════════════════════════════
    # AI PLAN GENERATION
    # ══════════════════════════════════════════════════════════════

    async def _ai_plan(self, query: str, intent: str, context: str) -> List[Dict]:
        """Generate an AI-powered execution plan."""
        brain = self._get_brain()
        mode_map = {
            "CODE": "CODING",
            "CREATIVE": "CREATIVE",
            "RESEARCH": "RESEARCH",
            "REASONING": "REASONING",
        }
        mode = mode_map.get(intent, "SMART")

        context_line = f"Past context: {context[:500]}" if context else ""
        system = (
            f"You are a planning engine. Create a step-by-step plan for this task.\n"
            f"Intent: {intent}\n"
            f"{context_line}\n\n"
            f'Return a JSON array of steps:\n'
            f'[{{"step": 1, "action": "description", "type": "{intent.lower()}"}}]\n'
            f"Max 5 steps. Return ONLY JSON."
        )

        try:
            response = await asyncio.wait_for(
                brain.generate_response(query, system_prompt=system, mode=mode),
                timeout=30.0,
            )
            cleaned = response.replace("```json", "").replace("```", "").strip()
            start = cleaned.find("[")
            end = cleaned.rfind("]") + 1
            if start != -1 and end > start:
                return json.loads(cleaned[start:end])
        except asyncio.TimeoutError:
            logger.warning("AI planning timed out")
        except json.JSONDecodeError as e:
            logger.warning(f"AI plan JSON parse failed: {e}")
        except Exception as e:
            logger.warning(f"AI planning failed: {e}")

        # Fallback: single-step plan
        return [{"step": 1, "action": query, "type": "general"}]

    # ══════════════════════════════════════════════════════════════
    # STEP EXECUTION (base)
    # ══════════════════════════════════════════════════════════════

    async def _execute_step(self, step, original_query: str) -> str:
        """Execute a single plan step, trying tools first then falling back to AI."""
        brain = self._get_brain()

        if isinstance(step, dict):
            action = step.get("action", original_query)
            step_type = step.get("type", "general")
        else:
            action = str(step)
            step_type = "general"

        # Try using tools via ToolRegistry
        try:
            from shell_tool_registry import ToolRegistry
            registry = ToolRegistry.get()

            if step_type == "web":
                results = registry.search("google_search")
                if results:
                    tool = results[0].tool_obj
                    return str(await tool(action))

            if step_type == "code":
                results = registry.search("code")
                if results:
                    for r in results[:1]:
                        try:
                            return str(await r.tool_obj(action))
                        except Exception:
                            pass
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"Tool routing failed for step type '{step_type}': {e}")

        # Fallback to AI reasoning
        mode_map = {
            "web": "RESEARCH",
            "code": "CODING",
            "creative": "CREATIVE",
            "research": "RESEARCH",
            "security": "REASONING",
            "data": "CODING",
            "system": "FAST",
            "file": "FAST",
            "automation": "CODING",
            "social": "SMART",
        }
        mode = mode_map.get(step_type, "SMART")

        try:
            return await asyncio.wait_for(
                brain.generate_response(action, mode=mode),
                timeout=30.0,
            )
        except asyncio.TimeoutError:
            return f"Step timed out: {action[:100]}"
        except Exception as e:
            return f"Step failed: {e}"

    # ══════════════════════════════════════════════════════════════
    # TOOL CHAINING WITH TEMPLATE SUBSTITUTION
    # ══════════════════════════════════════════════════════════════

    async def _execute_plan_with_chaining(self, plan: List, query: str,
                                          state: Optional[Dict] = None) -> List[str]:
        """
        Execute plan steps where each step can reference previous outputs.
        Use {{step_N_output}} in action text to inject prior step results.
        """
        step_outputs: Dict[str, str] = {}
        results: List[str] = []

        for i, step in enumerate(plan):
            # Extract action string
            if isinstance(step, dict):
                action = step.get("action", "")
            else:
                action = str(step)

            # Template substitution — replace {{step_N_output}} with actual output
            for key, value in step_outputs.items():
                placeholder = "{{" + key + "}}"
                action = action.replace(placeholder, str(value)[:500])

            # Update step with substituted action for execution
            if isinstance(step, dict):
                step = dict(step)
                step["action"] = action

            # Execute step with error recovery
            result = await self._execute_step_with_recovery(step, query)
            step_outputs[f"step_{i+1}_output"] = result
            results.append(result)

            # Store in working memory if available
            try:
                from brain.memory_core import memory_core as mc
                if hasattr(mc, 'working_memory'):
                    mc.working_memory.push(
                        f"Step {i+1}: {str(result)[:200]}",
                        context=str(action)[:100]
                    )
            except Exception:
                pass

        return results

    # ══════════════════════════════════════════════════════════════
    # ERROR RECOVERY WITH ALTERNATIVE STRATEGIES
    # ══════════════════════════════════════════════════════════════

    async def _execute_step_with_recovery(self, step, query: str, attempt: int = 0) -> str:
        """Execute step with automatic error recovery and alternative strategy generation."""
        try:
            result = await self._execute_step(step, query)
            if result and "error" not in str(result).lower()[:50]:
                return result
            raise ValueError(f"Step returned error: {str(result)[:100]}")
        except Exception as e:
            if attempt >= 2:
                return f"Failed after {attempt + 1} attempts: {str(e)[:100]}"

            # Generate alternative approach using AI
            brain = self._get_brain()
            action_str = step.get("action", str(step)) if isinstance(step, dict) else str(step)
            try:
                alternative = await asyncio.wait_for(
                    brain.generate_response(
                        f"The approach '{action_str[:200]}' failed with error: {str(e)[:200]}. "
                        f"Suggest a different approach to achieve the same goal. Be specific and actionable.",
                        mode="FAST"
                    ),
                    timeout=10.0
                )
                logger.info(f"Recovery attempt {attempt + 1}: trying alternative approach")
                # Recurse with the alternative as a plain string step
                return await self._execute_step_with_recovery(alternative, query, attempt + 1)
            except Exception as recovery_err:
                return f"Recovery failed: {str(e)[:100]} (recovery error: {str(recovery_err)[:50]})"

    # ══════════════════════════════════════════════════════════════
    # SELF-REFLECTION
    # ══════════════════════════════════════════════════════════════

    async def _self_reflect(self, query: str, initial_answer: str) -> str:
        """
        Review own answer for accuracy and completeness.
        If errors or gaps are found, return an improved version.
        """
        brain = self._get_brain()
        try:
            critique = await asyncio.wait_for(
                brain.generate_response(
                    f"Review this answer for accuracy and completeness. "
                    f"If you find errors or gaps, provide an improved answer. "
                    f"If it's good, return it as-is.\n\n"
                    f"Question: {query}\n\n"
                    f"Answer: {initial_answer[:2000]}",
                    mode="REASONING"
                ),
                timeout=15.0
            )
            if critique and len(critique) > 50:
                return critique
        except asyncio.TimeoutError:
            logger.debug("Self-reflection timed out, using original answer")
        except Exception as e:
            logger.debug(f"Self-reflection failed: {e}")
        return initial_answer

    # ══════════════════════════════════════════════════════════════
    # CONFIDENCE SCORING
    # ══════════════════════════════════════════════════════════════

    def _estimate_confidence(self, response: str, query: str) -> float:
        """
        Score confidence 0.0-1.0 based on language analysis.
        Examines hedging words, definitive language, evidence markers,
        and response length to estimate answer certainty.
        """
        if not response:
            return 0.0

        score = 0.7  # baseline
        resp_lower = response.lower()

        # Hedging reduces confidence
        hedge_count = sum(1 for w in self.HEDGE_WORDS if w in resp_lower)
        score -= hedge_count * 0.05

        # Definitive language increases confidence
        definitive_count = sum(1 for w in self.DEFINITIVE_WORDS if w in resp_lower)
        score += definitive_count * 0.03

        # Evidence markers (numbers, code blocks, URLs) increase confidence
        if any(c.isdigit() for c in response):
            score += 0.05
        if "```" in response:
            score += 0.05
        if "http" in response:
            score += 0.03

        # Very short responses = lower confidence
        if len(response) < 50:
            score -= 0.1

        # Very long, detailed responses = higher confidence
        if len(response) > 500:
            score += 0.05

        # Question marks in the answer suggest uncertainty
        if response.count("?") > 2:
            score -= 0.05

        return max(0.0, min(1.0, round(score, 2)))

    # ══════════════════════════════════════════════════════════════
    # PARALLEL REASONING
    # ══════════════════════════════════════════════════════════════

    async def _parallel_reason(self, query: str) -> Dict:
        """
        Execute 2 reasoning paths with different approaches simultaneously,
        then pick the best result based on confidence scoring.
        """
        brain = self._get_brain()

        async def path_a():
            return await brain.generate_response(
                f"Think carefully and analytically: {query}", mode="REASONING"
            )

        async def path_b():
            return await brain.generate_response(
                f"Think creatively and consider alternatives: {query}", mode="CREATIVE"
            )

        try:
            results = await asyncio.wait_for(
                asyncio.gather(path_a(), path_b(), return_exceptions=True),
                timeout=30.0
            )
            valid = [
                (r, self._estimate_confidence(r, query))
                for r in results
                if isinstance(r, str) and r.strip()
            ]
            if not valid:
                return {
                    "answer": "Could not generate response via parallel reasoning.",
                    "confidence": 0.0,
                    "method": "parallel_failed",
                }
            best = max(valid, key=lambda x: x[1])
            return {
                "answer": best[0],
                "confidence": best[1],
                "method": "parallel_reasoning",
            }
        except asyncio.TimeoutError:
            return {
                "answer": "Parallel reasoning timed out.",
                "confidence": 0.0,
                "method": "parallel_timeout",
            }
        except Exception as e:
            return {
                "answer": str(e),
                "confidence": 0.0,
                "method": "parallel_error",
            }

    # ══════════════════════════════════════════════════════════════
    # SYNTHESIS
    # ══════════════════════════════════════════════════════════════

    async def _synthesize(self, query: str, results: str) -> str:
        """Synthesize all step results into a coherent final answer."""
        brain = self._get_brain()
        prompt = (
            f"Synthesize a clear, well-structured answer to the user's question.\n"
            f"Question: {query}\n"
            f"Gathered Data:\n{results[:3000]}"
        )
        try:
            return await asyncio.wait_for(
                brain.generate_response(prompt, mode="FAST"),
                timeout=15.0,
            )
        except Exception:
            return results[:2000]

    # ══════════════════════════════════════════════════════════════
    # STATISTICS
    # ══════════════════════════════════════════════════════════════

    def get_stats(self) -> str:
        """Return execution statistics."""
        total = len(self._execution_history)
        if total == 0:
            return "HyperCortex V5: No executions yet."

        intents = {}
        for h in self._execution_history:
            i = h["intent"]
            intents[i] = intents.get(i, 0) + 1

        avg_time = sum(h["elapsed"] for h in self._execution_history) / total
        avg_conf = sum(h.get("confidence", 0.0) for h in self._execution_history) / total

        lines = [
            "HyperCortex God-Mode V5 Stats",
            f"Total Executions: {total}",
            f"Avg Execution Time: {avg_time:.2f}s",
            f"Avg Confidence: {avg_conf:.2f}",
            "Intent Distribution:",
        ]
        for intent, count in sorted(intents.items(), key=lambda x: -x[1]):
            lines.append(f"  {intent}: {count}")
        return "\n".join(lines)

    @property
    def execution_history(self) -> List[Dict]:
        """Access execution history."""
        return self._execution_history


class HyperCortexResult:
    """
    Structured result from omni_think. Supports str() for backward compatibility
    (returns just the answer text) while also providing structured access to
    trace, confidence, intent, elapsed time, and step count.
    """

    __slots__ = ("answer", "trace", "confidence", "intent", "elapsed", "steps_executed")

    def __init__(self, answer: str, trace: List[str], confidence: float,
                 intent: str, elapsed: float, steps_executed: int):
        self.answer = answer
        self.trace = trace
        self.confidence = confidence
        self.intent = intent
        self.elapsed = elapsed
        self.steps_executed = steps_executed

    def __str__(self) -> str:
        return self.answer

    def __repr__(self) -> str:
        return (
            f"HyperCortexResult(intent={self.intent!r}, confidence={self.confidence}, "
            f"elapsed={self.elapsed}s, steps={self.steps_executed})"
        )

    def __getitem__(self, key):
        """Dict-like access for backward compatibility."""
        return self.to_dict()[key]

    def get(self, key, default=None):
        """Dict-like get for backward compatibility."""
        return self.to_dict().get(key, default)

    def to_dict(self) -> Dict:
        return {
            "answer": self.answer,
            "trace": self.trace,
            "confidence": self.confidence,
            "intent": self.intent,
            "elapsed": self.elapsed,
            "steps_executed": self.steps_executed,
        }


# Singleton Instance
hyper_cortex = HyperCortex()
