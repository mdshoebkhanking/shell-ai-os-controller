"""
Thinking Engine - Deep Reasoning for Shell AI
================================================
Four advanced reasoning strategies:
  - TreeOfThought: explore multiple paths, score, pick the best
  - SelfCritic: critique and iteratively improve answers
  - ProblemDecomposer: break complex problems into sub-problems
  - AnalogyReasoner: solve by finding analogies from other domains

All classes use MultiAIBrain for AI calls.
"""

import asyncio
import json
import logging
import re
from typing import Dict, List, Optional, Any

logger = logging.getLogger("ThinkingEngine")


class TreeOfThought:
    """Explore multiple reasoning paths, score them, pick the best."""

    async def think(
        self, problem: str, brain, breadth: int = 3, depth: int = 2
    ) -> Dict:
        """
        Multi-path reasoning with scoring.

        Returns:
            {"answer": str, "paths_explored": int, "best_score": float}

        Level 0: Generate `breadth` initial approaches (varied temperatures)
        Level 1: For each approach, generate `breadth` continuations
        Evaluate: Score each leaf path (AI rates 1-10)
        Select: Return highest-scoring path
        """
        paths_explored = 0

        # Level 0: Generate initial approaches
        approaches_prompt = (
            f"Give {breadth} different approaches to solve this problem. "
            f"Return as a JSON array of strings, each describing a distinct approach.\n\n"
            f"Problem: {problem}"
        )

        try:
            approaches_raw = await asyncio.wait_for(
                brain.generate_response(
                    prompt=approaches_prompt,
                    mode="FAST",
                    use_cache=False,
                    temperature=0.9,
                ),
                timeout=15.0,
            )
            approaches = self._parse_json_array(approaches_raw, breadth)
        except (asyncio.TimeoutError, Exception) as e:
            logger.warning(f"[TreeOfThought] Failed to generate approaches: {e}")
            # Fallback: single direct approach
            try:
                fallback = await asyncio.wait_for(
                    brain.generate_response(
                        prompt=f"Solve this problem:\n{problem}",
                        mode="REASONING",
                        use_cache=False,
                    ),
                    timeout=20.0,
                )
                return {
                    "answer": fallback,
                    "paths_explored": 1,
                    "best_score": 5.0,
                }
            except Exception:
                return {
                    "answer": "Unable to generate a solution.",
                    "paths_explored": 0,
                    "best_score": 0.0,
                }

        if not approaches:
            approaches = [f"Direct approach: solve {problem} step by step"]

        # Level 1: Develop each approach into a full solution (parallel)
        async def develop_approach(approach: str) -> str:
            prompt = (
                f"Continue and develop this approach into a complete, detailed solution.\n\n"
                f"Problem: {problem}\n\n"
                f"Approach: {approach}\n\n"
                f"Provide the detailed solution."
            )
            try:
                result = await asyncio.wait_for(
                    brain.generate_response(
                        prompt=prompt,
                        mode="FAST",
                        use_cache=False,
                        temperature=0.7,
                    ),
                    timeout=15.0,
                )
                return result
            except Exception as e:
                logger.warning(f"[TreeOfThought] Develop failed: {e}")
                return approach  # use the approach itself as fallback

        tasks = [develop_approach(a) for a in approaches]
        try:
            solutions = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=30.0,
            )
        except asyncio.TimeoutError:
            solutions = [a for a in approaches]

        # Filter out exceptions
        valid_solutions = []
        for sol in solutions:
            if isinstance(sol, Exception):
                valid_solutions.append("Could not develop this approach.")
            else:
                valid_solutions.append(sol)
            paths_explored += 1

        # Evaluate: Score each solution (parallel)
        async def score_solution(solution: str) -> float:
            score_prompt = (
                f"Rate this solution on a scale of 1 to 10 for correctness, "
                f"completeness, and clarity. Return ONLY a single number.\n\n"
                f"Problem: {problem}\n\n"
                f"Solution: {solution}"
            )
            try:
                result = await asyncio.wait_for(
                    brain.generate_response(
                        prompt=score_prompt,
                        mode="REASONING",
                        use_cache=False,
                        max_tokens=10,
                    ),
                    timeout=10.0,
                )
                return self._parse_score(result)
            except Exception:
                return 5.0  # neutral score on failure

        score_tasks = [score_solution(s) for s in valid_solutions]
        try:
            scores = await asyncio.wait_for(
                asyncio.gather(*score_tasks, return_exceptions=True),
                timeout=20.0,
            )
        except asyncio.TimeoutError:
            scores = [5.0] * len(valid_solutions)

        # Replace exceptions with neutral scores
        final_scores = []
        for s in scores:
            if isinstance(s, Exception):
                final_scores.append(5.0)
            else:
                final_scores.append(s)

        # Select best
        best_idx = 0
        best_score = 0.0
        for i, sc in enumerate(final_scores):
            if sc > best_score:
                best_score = sc
                best_idx = i

        return {
            "answer": valid_solutions[best_idx],
            "paths_explored": paths_explored,
            "best_score": best_score,
        }

    @staticmethod
    def _parse_json_array(raw: str, max_items: int) -> List[str]:
        """Extract a JSON array of strings from AI response."""
        # Try direct JSON parse
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return [str(item) for item in data[:max_items]]
        except json.JSONDecodeError:
            pass

        # Try to find JSON array in the response
        match = re.search(r'\[.*?\]', raw, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
                if isinstance(data, list):
                    return [str(item) for item in data[:max_items]]
            except json.JSONDecodeError:
                pass

        # Fallback: split by numbered lines
        lines = []
        for line in raw.strip().split('\n'):
            cleaned = re.sub(r'^\s*\d+[\.\)]\s*', '', line).strip()
            if cleaned and len(cleaned) > 5:
                lines.append(cleaned)
        return lines[:max_items] if lines else []

    @staticmethod
    def _parse_score(raw: str) -> float:
        """Extract a numeric score from AI response."""
        match = re.search(r'(\d+(?:\.\d+)?)', raw.strip())
        if match:
            score = float(match.group(1))
            return max(1.0, min(10.0, score))
        return 5.0


class SelfCritic:
    """Critique own answers and improve them iteratively."""

    async def critique_and_revise(
        self, answer: str, question: str, brain, max_rounds: int = 2
    ) -> Dict:
        """
        Iteratively critique and revise an answer.

        Returns:
            {"final_answer": str, "rounds": int, "improved": bool}
        """
        current_answer = answer
        improved = False

        for round_num in range(1, max_rounds + 1):
            # Generate critique
            critique_prompt = (
                f"Critically evaluate this answer. Identify any errors, "
                f"gaps, logical flaws, or areas for improvement. "
                f"If the answer is already excellent, say 'no significant issues'.\n\n"
                f"Question: {question}\n\n"
                f"Answer: {current_answer}"
            )

            try:
                critique = await asyncio.wait_for(
                    brain.generate_response(
                        prompt=critique_prompt,
                        mode="REASONING",
                        use_cache=False,
                    ),
                    timeout=15.0,
                )
            except Exception as e:
                logger.warning(f"[SelfCritic] Critique failed round {round_num}: {e}")
                break

            # Check if critique says answer is already good
            critique_lower = critique.lower()
            stop_phrases = [
                "no significant issues",
                "looks good",
                "no major issues",
                "well-written",
                "comprehensive and accurate",
                "no improvements needed",
                "excellent answer",
            ]
            if any(phrase in critique_lower for phrase in stop_phrases):
                logger.info(
                    f"[SelfCritic] Answer accepted at round {round_num}, no issues found"
                )
                break

            # Revise based on critique
            revise_prompt = (
                f"Revise and improve the answer based on this critique. "
                f"Provide the complete improved answer.\n\n"
                f"Question: {question}\n\n"
                f"Original answer: {current_answer}\n\n"
                f"Critique: {critique}"
            )

            try:
                revised = await asyncio.wait_for(
                    brain.generate_response(
                        prompt=revise_prompt,
                        mode="SMART",
                        use_cache=False,
                    ),
                    timeout=15.0,
                )
                current_answer = revised
                improved = True
            except Exception as e:
                logger.warning(f"[SelfCritic] Revision failed round {round_num}: {e}")
                break

        return {
            "final_answer": current_answer,
            "rounds": round_num if 'round_num' in dir() else 0,
            "improved": improved,
        }


class ProblemDecomposer:
    """Break complex problems into sub-problems and solve each."""

    async def decompose(self, problem: str, brain) -> List[str]:
        """
        Decompose a complex problem into 2-4 independent sub-problems.
        Returns list of sub-problem strings. Falls back to [problem] if parsing fails.
        """
        decompose_prompt = (
            f"Break this problem into 2 to 4 independent sub-problems that "
            f"can be solved separately. Return as a JSON array of strings.\n\n"
            f"Problem: {problem}"
        )

        try:
            raw = await asyncio.wait_for(
                brain.generate_response(
                    prompt=decompose_prompt,
                    mode="REASONING",
                    use_cache=False,
                ),
                timeout=15.0,
            )
            sub_problems = self._parse_sub_problems(raw)
            if sub_problems:
                return sub_problems
        except Exception as e:
            logger.warning(f"[ProblemDecomposer] Decomposition failed: {e}")

        return [problem]

    async def solve_decomposed(self, problem: str, brain) -> str:
        """
        Decompose the problem, solve each sub-problem independently,
        then synthesize results into a final answer.
        """
        sub_problems = await self.decompose(problem, brain)

        if len(sub_problems) == 1 and sub_problems[0] == problem:
            # Could not decompose; solve directly
            try:
                return await asyncio.wait_for(
                    brain.generate_response(
                        prompt=f"Solve this problem thoroughly:\n{problem}",
                        mode="REASONING",
                        use_cache=False,
                    ),
                    timeout=20.0,
                )
            except Exception:
                return "Unable to solve the problem."

        # Solve each sub-problem in parallel
        async def solve_sub(sub: str) -> str:
            prompt = (
                f"Solve this sub-problem completely:\n\n{sub}\n\n"
                f"(This is part of the larger problem: {problem})"
            )
            try:
                return await asyncio.wait_for(
                    brain.generate_response(
                        prompt=prompt,
                        mode="SMART",
                        use_cache=False,
                    ),
                    timeout=15.0,
                )
            except Exception as e:
                logger.warning(f"[ProblemDecomposer] Sub-problem solve failed: {e}")
                return f"Could not solve: {sub}"

        tasks = [solve_sub(sp) for sp in sub_problems]
        try:
            sub_solutions = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=30.0,
            )
        except asyncio.TimeoutError:
            sub_solutions = [f"Timed out solving: {sp}" for sp in sub_problems]

        # Replace exceptions
        clean_solutions = []
        for i, sol in enumerate(sub_solutions):
            if isinstance(sol, Exception):
                clean_solutions.append(f"Failed to solve sub-problem {i+1}")
            else:
                clean_solutions.append(sol)

        # Synthesize
        parts_text = "\n\n".join(
            f"Sub-problem {i+1}: {sub_problems[i]}\nSolution: {clean_solutions[i]}"
            for i in range(len(sub_problems))
        )

        synthesis_prompt = (
            f"Combine these sub-problem solutions into one coherent, "
            f"complete answer to the original problem.\n\n"
            f"Original problem: {problem}\n\n"
            f"{parts_text}"
        )

        try:
            final = await asyncio.wait_for(
                brain.generate_response(
                    prompt=synthesis_prompt,
                    mode="SMART",
                    use_cache=False,
                ),
                timeout=15.0,
            )
            return final
        except Exception:
            # Return concatenated sub-solutions as fallback
            return "\n\n".join(
                f"Part {i+1}: {s}" for i, s in enumerate(clean_solutions)
            )

    @staticmethod
    def _parse_sub_problems(raw: str) -> List[str]:
        """Extract sub-problems from AI response."""
        # Try JSON parse
        try:
            data = json.loads(raw)
            if isinstance(data, list) and len(data) >= 2:
                return [str(item) for item in data[:4]]
        except json.JSONDecodeError:
            pass

        # Try finding JSON array
        match = re.search(r'\[.*?\]', raw, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
                if isinstance(data, list) and len(data) >= 2:
                    return [str(item) for item in data[:4]]
            except json.JSONDecodeError:
                pass

        # Fallback: numbered lines
        lines = []
        for line in raw.strip().split('\n'):
            cleaned = re.sub(r'^\s*\d+[\.\)]\s*', '', line).strip()
            if cleaned and len(cleaned) > 10:
                lines.append(cleaned)
        return lines[:4] if len(lines) >= 2 else []


class AnalogyReasoner:
    """Reason by finding analogies to known problems."""

    async def reason_by_analogy(
        self, problem: str, brain, memory=None
    ) -> str:
        """
        Solve a problem by analogy.

        1. If memory is available, search for similar past problems
        2. If a similar past solution is found, adapt it
        3. Otherwise, find an analogy from a different domain
        4. Generate solution using the analogy
        """
        past_context = None

        # Step 1: Search memory for similar past problems
        if memory is not None:
            try:
                # Try common memory interface patterns
                if hasattr(memory, 'search'):
                    results = await self._safe_memory_search(memory, problem)
                    if results:
                        past_context = results
                elif hasattr(memory, 'recall'):
                    results = await self._safe_memory_recall(memory, problem)
                    if results:
                        past_context = results
            except Exception as e:
                logger.warning(f"[AnalogyReasoner] Memory search failed: {e}")

        # Step 2/3: Build prompt based on whether we have past context
        if past_context:
            analogy_prompt = (
                f"I found a similar past problem and its solution:\n\n"
                f"{past_context}\n\n"
                f"Now apply the same approach to solve this new problem:\n\n"
                f"{problem}\n\n"
                f"Explain how the analogy applies and provide a complete solution."
            )
        else:
            analogy_prompt = (
                f"Find an analogy from a different domain or field that "
                f"relates to this problem. Use that analogy to reason about "
                f"and solve the problem.\n\n"
                f"Problem: {problem}\n\n"
                f"Steps:\n"
                f"1. Identify a similar problem from another domain\n"
                f"2. Explain the parallel between them\n"
                f"3. Apply the analogous solution to this problem\n"
                f"4. Provide a complete answer"
            )

        try:
            solution = await asyncio.wait_for(
                brain.generate_response(
                    prompt=analogy_prompt,
                    mode="REASONING",
                    use_cache=False,
                    temperature=0.8,
                ),
                timeout=20.0,
            )
            return solution
        except Exception as e:
            logger.warning(f"[AnalogyReasoner] Analogy reasoning failed: {e}")
            # Direct fallback
            try:
                return await asyncio.wait_for(
                    brain.generate_response(
                        prompt=f"Solve this problem:\n{problem}",
                        mode="SMART",
                        use_cache=False,
                    ),
                    timeout=15.0,
                )
            except Exception:
                return "Unable to reason about this problem."

    @staticmethod
    async def _safe_memory_search(memory, query: str) -> Optional[str]:
        """Safely call memory.search, handling sync and async."""
        result = memory.search(query)
        if asyncio.iscoroutine(result):
            result = await result
        if result:
            if isinstance(result, list):
                return "\n".join(str(r) for r in result[:3])
            return str(result)
        return None

    @staticmethod
    async def _safe_memory_recall(memory, query: str) -> Optional[str]:
        """Safely call memory.recall, handling sync and async."""
        result = memory.recall(query)
        if asyncio.iscoroutine(result):
            result = await result
        if result:
            if isinstance(result, list):
                return "\n".join(str(r) for r in result[:3])
            return str(result)
        return None


class ThinkingEngine:
    """
    Unified entry point for all deep thinking strategies.
    Wraps TreeOfThought, SelfCritic, ProblemDecomposer, and AnalogyReasoner.
    """

    def __init__(self):
        self._tree = TreeOfThought()
        self._critic = SelfCritic()
        self._decomposer = ProblemDecomposer()
        self._analogy = AnalogyReasoner()

    async def tree_of_thought(
        self, problem: str, brain, breadth: int = 3, depth: int = 2
    ) -> Dict:
        """Explore multiple reasoning paths and pick the best."""
        return await self._tree.think(problem, brain, breadth=breadth, depth=depth)

    async def self_critique(
        self, answer: str, question: str, brain, max_rounds: int = 2
    ) -> Dict:
        """Critique and iteratively improve an answer."""
        return await self._critic.critique_and_revise(
            answer, question, brain, max_rounds=max_rounds
        )

    async def decompose(self, problem: str, brain) -> str:
        """Decompose a complex problem and solve each part."""
        return await self._decomposer.solve_decomposed(problem, brain)

    async def reason_by_analogy(
        self, problem: str, brain, memory=None
    ) -> str:
        """Solve by finding and applying analogies."""
        return await self._analogy.reason_by_analogy(problem, brain, memory=memory)


# Singleton instance
thinking_engine = ThinkingEngine()
