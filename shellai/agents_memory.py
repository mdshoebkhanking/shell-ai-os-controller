from __future__ import annotations

from typing import Any, List, Optional

from shellai.agents import BaseAgent
from shellai.config import ShellAIConfig
from shellai.memory import MemoryStore
from shellai.observability import RequestTrace, TRACE_STORE
from shellai.protocol import AgentRole
from shellai.skills import SkillManager


class MemoryAgent(BaseAgent):
    """High-level memory facade for CoordinatorAgent and future fabric agents."""

    def __init__(
        self,
        config: Optional[ShellAIConfig] = None,
        memory_store: Optional[MemoryStore] = None,
        skill_manager: Optional[SkillManager] = None,
        trace: Optional[RequestTrace] = None,
    ) -> None:
        self.config = config or ShellAIConfig.load()
        self.memory_store = memory_store or MemoryStore(self.config.paths.memory_db, config=self.config)
        self.skill_manager = skill_manager or SkillManager(config=self.config, memory_store=self.memory_store)
        super().__init__(AgentRole.MEMORY, trace or TRACE_STORE.start_trace(""))

    def bind_trace(self, trace: RequestTrace) -> "MemoryAgent":
        self.trace = trace
        return self

    def get_context_bundle(self, user_text: str, context: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        query = str(user_text or "").strip() or "recent task"
        self.record("context_start", "assembling memory context", {"query": query[:160]})
        profile = self.memory_store.get_user_profile()
        recent_tasks = self.memory_store.search_memory("conversation", query, limit=5, trace=self.trace)
        relevant_skills = self.find_relevant_skills(query)
        bundle = {
            "user_profile": profile,
            "recent_tasks": recent_tasks,
            "relevant_skills": relevant_skills,
            "context": dict(context or {}),
        }
        self.record(
            "context_ready",
            "memory context assembled",
            {"recent_tasks": len(recent_tasks), "relevant_skills": len(relevant_skills)},
        )
        return bundle

    def save_task_result(
        self,
        task_info: dict[str, Any],
        tools_used: List[dict[str, Any]],
        summary: dict[str, Any],
        outcome_status: str,
    ) -> dict[str, Any]:
        user_summary = str(summary.get("user_summary") or summary.get("summary") or "")
        memory_summary = str(summary.get("memory_summary") or user_summary)
        payload = {
            "conversation_id": task_info.get("conversation_id") or self.trace.request_id,
            "agent_role": task_info.get("agent_role") or AgentRole.COORDINATOR,
            "user_input": str(task_info.get("user_input") or task_info.get("text") or ""),
            "agent_output": user_summary,
            "summary": memory_summary,
            "metadata": {
                "tools_used": list(tools_used or []),
                "outcome_status": str(outcome_status or ""),
                "task_info": dict(task_info or {}),
            },
        }
        result = self.memory_store.save_memory("conversation", payload, trace=self.trace)
        self.record("saved_task", "saved task result", {"status": outcome_status, "result": result})
        return result

    def find_relevant_skills(self, user_text: str) -> List[dict[str, Any]]:
        skills = self.skill_manager.list_skills(query=str(user_text or ""), register=True)
        if not skills:
            skills = self.skill_manager.list_skills(register=True)[:5]
        compact = [
            {
                "id": skill.get("id") or skill.get("skill_id"),
                "name": skill.get("name"),
                "description": skill.get("description", ""),
                "tags": list(skill.get("tags") or []),
            }
            for skill in skills
        ]
        self.record("skills_found", "looked up relevant skills", {"count": len(compact)})
        return compact

    def update_profile(self, patch: dict[str, Any]) -> dict[str, Any]:
        profile = self.memory_store.update_user_profile(dict(patch or {}), trace=self.trace)
        self.record("profile_updated", "updated user profile", {"keys": sorted((patch or {}).keys())})
        return profile


__all__ = ["MemoryAgent"]
