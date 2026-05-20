from __future__ import annotations

import json
import os
from typing import Any, Optional

from shellai.agents import BaseAgent
from shellai.config import ShellAIConfig
from shellai.models import ModelRouter
from shellai.observability import RequestTrace, TRACE_STORE
from shellai.protocol import AgentRole


class UIAgent(BaseAgent):
    """Formats internal task results for CLI and desktop surfaces."""

    def __init__(
        self,
        config: Optional[ShellAIConfig] = None,
        model_router: Optional[Any] = None,
        trace: Optional[RequestTrace] = None,
    ) -> None:
        self.config = config or ShellAIConfig.load()
        self.model_router = model_router or ModelRouter(self.config)
        super().__init__(AgentRole.UI, trace or TRACE_STORE.start_trace(""))

    def bind_trace(self, trace: RequestTrace) -> "UIAgent":
        self.trace = trace
        return self

    def shape_response(
        self,
        result: dict[str, Any],
        *,
        user_text: str = "",
        user_profile: Optional[dict[str, Any]] = None,
    ) -> dict[str, str]:
        profile = dict(user_profile or {})
        preferences = dict(profile.get("preferences") or profile or {})
        language_style = str(
            preferences.get("language_style")
            or preferences.get("preferred_explanation_style")
            or self.config.user_profile.get("language_style")
            or "English"
        )
        self.record("format_start", "formatting response", {"language_style": language_style[:120]})

        if os.environ.get("SHELLAI_UI_MODEL_SUMMARY", "").strip().lower() in {"1", "true", "yes", "on"}:
            model_result = self._try_model_shape(result, user_text=user_text, language_style=language_style)
            if model_result:
                return model_result

        cli_summary = self._deterministic_cli(result, language_style)
        desktop_summary = self._deterministic_desktop(result, language_style)
        shaped = {
            "cli_summary": cli_summary,
            "desktop_summary": desktop_summary,
            "language_style": language_style,
        }
        self.record("format_ready", "response formatted", {"model_used": False})
        return shaped

    def _try_model_shape(self, result: dict[str, Any], *, user_text: str, language_style: str) -> Optional[dict[str, str]]:
        prompt = (
            "Return JSON with cli_summary and desktop_summary for this ShellAI result. "
            "Keep commands/code in English. Match this language style for explanations: "
            f"{language_style}\nUser text: {user_text}\nResult:\n"
            + json.dumps(result, ensure_ascii=False, sort_keys=True)[:6000]
        )
        try:
            response = self.model_router.complete(prompt, model_role="summarization")
            data = json.loads(str(response.text or "{}"))
            cli_summary = str(data.get("cli_summary") or "").strip()
            desktop_summary = str(data.get("desktop_summary") or cli_summary).strip()
            if cli_summary and desktop_summary:
                self.record("format_ready", "response formatted with model", {"model_used": True})
                return {
                    "cli_summary": cli_summary,
                    "desktop_summary": desktop_summary,
                    "language_style": language_style,
                }
        except Exception as exc:
            self.record("format_fallback", "UI model formatting failed", {"error": str(exc)})
        return None

    @staticmethod
    def _deterministic_cli(result: dict[str, Any], language_style: str) -> str:
        status = str(result.get("status") or "unknown")
        summary = str(result.get("summary") or result.get("message") or "").strip()
        if not summary:
            summary = f"Task finished with status: {status}."
        steps = result.get("steps") if isinstance(result.get("steps"), list) else []
        if not steps:
            return f"{summary} [{status}]"
        compact = ", ".join(
            f"{step.get('tool', 'tool')}={step.get('status', 'unknown')}"
            for step in steps[:5]
            if isinstance(step, dict)
        )
        return f"{summary} [{status}; {compact}]"

    @staticmethod
    def _deterministic_desktop(result: dict[str, Any], language_style: str) -> str:
        status = str(result.get("status") or "unknown")
        summary = str(result.get("summary") or result.get("message") or "").strip()
        if not summary:
            summary = "Request complete."
        if "hindi" in language_style.lower() or "hinglish" in language_style.lower():
            prefix = "Ho gaya" if status == "ok" else "Dhyan de"
            return f"{prefix}: {summary}"
        return summary


__all__ = ["UIAgent"]
