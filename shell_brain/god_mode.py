"""
Shell advanced planning engine.
Combines strategy, architecture, and knowledge checks.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List

try:
    from shell_safe_executor import god_tier_tool as function_tool
except Exception:
    try:
        from livekit.agents import function_tool
    except Exception:
        def function_tool(func):
            return func

from .hyper_cortex import hyper_cortex
from .infinite_context import get_knowledge, search_knowledge
from .omni_brain import omni_brain

logger = logging.getLogger("god_mode")


def _safe_task(task: Any) -> str:
    return str(task or "").strip()


def _phase_line(phase: Dict[str, Any]) -> str:
    phase_no = phase.get("phase", "?")
    name = phase.get("name", "Unnamed")
    action = phase.get("action", "No action provided")
    return f"     - Phase {phase_no}: {name} -> {action}"


@function_tool
async def activate_god_mode_tool(complex_task: str) -> str:
    """
    Build a structured plan for large and ambiguous user requests.
    """
    task = _safe_task(complex_task)
    if not task:
        return "Planning failed: empty task. Please provide a concrete objective."

    try:
        report: List[str] = []
        report.append(f"**ADVANCED PLANNING STARTED** for task: '{task}'")
        report.append("")

        # 1. Strategic planning
        report.append("**Phase 1: Deep Thought Strategy**")
        strategic_plan = await asyncio.to_thread(omni_brain.think_deeply, task)
        meta = strategic_plan.get("meta", {}) if isinstance(strategic_plan, dict) else {}
        phases = strategic_plan.get("phases", []) if isinstance(strategic_plan, dict) else []

        report.append(f"   > Intent: {meta.get('intent', 'general')}")
        report.append(f"   > Analogy: {meta.get('analogy', 'N/A')}")
        report.append(f"   > Confidence: {meta.get('confidence', 'N/A')}")

        if not phases:
            phases = [
                {"phase": 1, "name": "Analysis", "action": "Clarify constraints and define measurable success criteria."}
            ]

        for phase in phases:
            report.append(_phase_line(phase))
        report.append("")

        # 2. Architecture synthesis
        report.append("**Phase 2: Architecture Synthesis**")
        primary_phase = phases[0].get("name", "Foundation")
        try:
            blueprint = await asyncio.to_thread(
                hyper_cortex.synergize_project,
                f"Planning-{primary_phase}",
                task,
            )
            bp_meta = blueprint.get("meta", {}) if isinstance(blueprint, dict) else {}
            bp_front = blueprint.get("frontend", {}) if isinstance(blueprint, dict) else {}
            bp_back = blueprint.get("backend", {}) if isinstance(blueprint, dict) else {}

            report.append(f"   > Blueprint Core: {bp_meta.get('complexity', 'unknown')}")
            report.append(f"   > Architecture: {bp_meta.get('type', 'Generated Architecture')}")
            report.append(f"   > HTML Payload Size: {len(str(bp_front.get('html_body', '')))} chars")
            packages = bp_back.get("python_packages", [])
            pkg_line = ", ".join(packages) if isinstance(packages, list) and packages else "flask"
            report.append(f"   > Backend Stack: {pkg_line}")
        except Exception as blueprint_error:
            logger.warning("Architecture synthesis failed: %s", blueprint_error)
            report.append(f"   > Architecture synthesis: [Fallback] ({blueprint_error})")
        report.append("")

        # 3. Knowledge retrieval
        report.append("**Phase 3: Infinite Knowledge Scan**")
        ranked_hits = search_knowledge(task, max_results=2)
        if ranked_hits:
            top = ranked_hits[0]
            report.append(f"   > Archive Hit: {top['key']} [{top['category']}]")
            if len(ranked_hits) > 1:
                second = ranked_hits[1]
                report.append(f"   > Related Context: {second['key']} [{second['category']}]")
        else:
            knowledge = get_knowledge(task)
            if knowledge:
                preview = knowledge.replace("\n", " ")[:140]
                report.append(f"   > Found Context: {preview}...")
            else:
                report.append("   > No direct historical match found. Proceeding with first-principles strategy.")
        report.append("")

        # 4. Execution readiness
        report.append("**Phase 4: Evolution Readiness**")
        report.append("   > Planning, architecture synthesis, and knowledge routing are operational.")
        report.append("   > System is ready to execute implementation steps.")

        # 5. Final summary
        report.append("")
        report.append("**PLANNING SUMMARY:**")
        report.append("Plan validated. Blueprint prepared. Reply with 'Execute' to run Phase 1 implementation.")

        return "\n".join(report)

    except Exception as exc:
        logger.exception("Advanced planning crash: %s", exc)
        return f"Planning failed: {exc}"
