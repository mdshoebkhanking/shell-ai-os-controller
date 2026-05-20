from __future__ import annotations

from collections import Counter
from typing import Any, List, Optional

from shellai.agents import BaseAgent
from shellai.config import ShellAIConfig
from shellai.memory import MemoryStore
from shellai.monitor import list_trace_snapshots
from shellai.observability import RequestTrace, TRACE_STORE
from shellai.policy import read_audit_log
from shellai.protocol import AgentRole


class OptimizerAgent(BaseAgent):
    """Read-only suggestion engine over traces, memories, skills, and audit logs."""

    def __init__(
        self,
        config: Optional[ShellAIConfig] = None,
        memory_store: Optional[MemoryStore] = None,
        trace: Optional[RequestTrace] = None,
    ) -> None:
        self.config = config or ShellAIConfig.load()
        self.memory_store = memory_store or MemoryStore(self.config.paths.memory_db, config=self.config)
        super().__init__(AgentRole.OPTIMIZER, trace or TRACE_STORE.start_trace(""))

    def generate_report(self, *, limit: int = 100) -> dict[str, Any]:
        self.record("report_start", "generating optimizer suggestions")
        traces = list_trace_snapshots(self.config, limit=limit)
        audits = read_audit_log(self.config, limit=limit)
        skills = self.memory_store.list_skills({"limit": limit})
        conversations = self.memory_store.search_memory("conversation", "", limit=limit, trace=self.trace)
        suggestions: List[dict[str, Any]] = []
        suggestions.extend(self._recurring_task_suggestions(traces, conversations))
        suggestions.extend(self._safety_suggestions(audits))
        suggestions.extend(self._failure_suggestions(traces))
        suggestions.extend(self._skill_usage_suggestions(skills))
        report = {
            "status": "ok",
            "suggestions": suggestions,
            "counts": {
                "traces": len(traces),
                "audit_entries": len(audits),
                "skills": len(skills),
                "conversations": len(conversations),
            },
            "mutated": False,
        }
        self.record("report_ready", "optimizer report ready", {"suggestions": len(suggestions)})
        return report

    @staticmethod
    def _recurring_task_suggestions(traces: List[dict[str, Any]], conversations: List[dict[str, Any]]) -> List[dict[str, Any]]:
        texts = [str(row.get("user_input") or "").strip() for row in traces]
        texts.extend(str(row.get("user_input") or "").strip() for row in conversations)
        counter = Counter(text for text in texts if text)
        suggestions = []
        for text, count in counter.most_common(5):
            if count >= 2:
                suggestions.append({
                    "type": "skill_candidate",
                    "severity": "info",
                    "title": "Recurring task detected",
                    "message": f"'{text[:120]}' appeared {count} times. Consider saving it as a reusable skill.",
                    "metadata": {"task": text, "count": count},
                })
        return suggestions

    @staticmethod
    def _safety_suggestions(audits: List[dict[str, Any]]) -> List[dict[str, Any]]:
        by_command = Counter(
            str(row.get("command") or "")
            for row in audits
            if str(row.get("level") or "") in {"ASK", "BLOCK"}
        )
        suggestions = []
        for command, count in by_command.most_common(5):
            if command and count >= 2:
                suggestions.append({
                    "type": "safety_pattern",
                    "severity": "warning",
                    "title": "Repeated safety decision",
                    "message": f"'{command[:120]}' triggered ASK/BLOCK {count} times. Review policy or create a safer workflow.",
                    "metadata": {"command": command, "count": count},
                })
        return suggestions

    @staticmethod
    def _failure_suggestions(traces: List[dict[str, Any]]) -> List[dict[str, Any]]:
        failures = [row for row in traces if str(row.get("status")) in {"error", "blocked", "needs_confirmation"}]
        if not failures:
            return []
        return [{
            "type": "failure_review",
            "severity": "warning",
            "title": "Recent failed or blocked tasks",
            "message": f"{len(failures)} recent task(s) need review. Inspect `shellai monitor --errors`.",
            "metadata": {"count": len(failures)},
        }]

    @staticmethod
    def _skill_usage_suggestions(skills: List[dict[str, Any]]) -> List[dict[str, Any]]:
        suggestions = []
        unused = [
            skill for skill in skills
            if int(skill.get("success_count") or 0) == 0 and int(skill.get("failure_count") or 0) == 0
        ]
        if len(unused) >= 3:
            suggestions.append({
                "type": "skill_cleanup",
                "severity": "info",
                "title": "Unused skills",
                "message": f"{len(unused)} skills have no usage yet. Review or test them before relying on them.",
                "metadata": {"count": len(unused)},
            })
        return suggestions


__all__ = ["OptimizerAgent"]
