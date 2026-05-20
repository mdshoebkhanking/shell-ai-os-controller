from __future__ import annotations

import json
import platform
import re
import time
import uuid
from dataclasses import dataclass
from typing import Any

from shellai.agents import CoordinatorAgent
from shellai.agents_memory import MemoryAgent
from shellai.agents_ui import UIAgent
from shellai.config import ShellAIConfig
from shellai.memory import MemoryStore
from shellai.models import MissingProviderCredentialError, ModelCallError, ModelRouter
from shellai.monitor import record_trace_snapshot
from shellai.observability import RequestTrace, TRACE_STORE, get_logger
from shellai.protocol import AgentMessage, AgentRole, MessageKind
from shellai.skills import SkillManager
from shellai.tools import ToolRegistry, ToolRequest, ToolResult


PLAN_SCHEMA_VERSION = "1.0"
SUPPORTED_PLAN_TOOLS = {"shell", "file", "os"}


class AgentPlanError(ValueError):
    pass


@dataclass
class AgentLoopServices:
    config: ShellAIConfig
    model_router: Any
    memory_store: MemoryStore | None
    skill_manager: SkillManager | None
    tool_registry: ToolRegistry
    warnings: list[str]
    memory_agent: Any | None = None
    ui_agent: Any | None = None
    agent_runtime: Any | None = None


def create_user_request(
    text: str,
    *,
    context: dict[str, Any] | None = None,
    auto_approve_ask: bool = False,
) -> AgentMessage:
    metadata = {
        "context": dict(context or {}),
        "auto_approve_ask": bool(auto_approve_ask),
    }
    return AgentMessage.create(
        sender=AgentRole.UI,
        recipient=AgentRole.COORDINATOR,
        kind=MessageKind.USER_REQUEST,
        content=str(text or ""),
        metadata=metadata,
    )


def _extract_json_object(text: str) -> dict[str, Any]:
    raw = str(text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            raise AgentPlanError("Planning model did not return a JSON object")
        try:
            payload = json.loads(raw[start:end + 1])
        except json.JSONDecodeError as exc:
            raise AgentPlanError(f"Planning JSON is invalid: {exc}") from exc
    if not isinstance(payload, dict):
        raise AgentPlanError("Planning JSON must be an object")
    return payload


def _validate_plan(plan: dict[str, Any]) -> dict[str, Any]:
    steps = plan.get("steps")
    if not isinstance(steps, list) or not steps:
        raise AgentPlanError("Plan must include a non-empty steps list")
    normalized_steps: list[dict[str, Any]] = []
    for index, raw_step in enumerate(steps, start=1):
        if not isinstance(raw_step, dict):
            raise AgentPlanError(f"Plan step {index} must be an object")
        tool = str(raw_step.get("tool") or "").strip()
        if tool not in SUPPORTED_PLAN_TOOLS:
            raise AgentPlanError(f"Plan step {index} has unsupported tool: {tool}")
        args = raw_step.get("args")
        if args is None and tool == "shell":
            args = {"command": raw_step.get("command")}
        if not isinstance(args, dict):
            raise AgentPlanError(f"Plan step {index} args must be an object")
        normalized_steps.append({
            "id": str(raw_step.get("id") or f"step_{index}"),
            "tool": tool,
            "description": str(raw_step.get("description") or f"Run {tool}"),
            "args": args,
            "dry_run": bool(raw_step.get("dry_run", False)),
        })
    normalized = dict(plan)
    normalized["schema_version"] = str(plan.get("schema_version") or PLAN_SCHEMA_VERSION)
    normalized["steps"] = normalized_steps
    normalized["mark_reusable"] = bool(plan.get("mark_reusable", False))
    normalized["skills"] = list(plan.get("skills") or [])
    normalized["user_message"] = str(plan.get("user_message") or "")
    return normalized


def _explicit_shell_command(text: str) -> str:
    clean = str(text or "").strip()
    for prefix in ("shell:", "!", "$"):
        if clean.startswith(prefix):
            return clean[len(prefix):].strip()
    return ""


def _deterministic_shell_plan(command: str) -> dict[str, Any]:
    return _validate_plan({
        "schema_version": PLAN_SCHEMA_VERSION,
        "user_message": "Explicit shell command request.",
        "mark_reusable": False,
        "steps": [
            {
                "id": "step_1",
                "tool": "shell",
                "description": "Run explicit shell command.",
                "args": {"command": command},
                "dry_run": False,
            }
        ],
    })


def _safe_preview(value: Any, limit: int = 1200) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True) if not isinstance(value, str) else value
    return text[:limit]


class AgentLoop:
    def __init__(
        self,
        *,
        config: ShellAIConfig | None = None,
        model_router: Any | None = None,
        memory_store: MemoryStore | None = None,
        skill_manager: SkillManager | None = None,
        tool_registry: ToolRegistry | None = None,
        agent_runtime: Any | None = None,
    ) -> None:
        self.config = config or ShellAIConfig.load()
        self.logger = get_logger("shellai.agent_loop")
        self._provided_memory_store = memory_store
        self._provided_skill_manager = skill_manager
        self._provided_tool_registry = tool_registry
        self._provided_model_router = model_router
        self._provided_agent_runtime = agent_runtime

    def _services(self, trace: RequestTrace) -> AgentLoopServices:
        warnings: list[str] = []
        runtime = self._provided_agent_runtime
        if runtime is not None:
            try:
                runtime.bind_trace(trace)
            except Exception as exc:
                warnings.append(f"agent runtime bind failed: {exc}")
        model_router = self._provided_model_router or ModelRouter(self.config)
        memory_store = self._provided_memory_store
        if memory_store is None and runtime is not None:
            memory_store = getattr(runtime, "memory_store", None)
        if memory_store is None:
            try:
                memory_store = MemoryStore(self.config.paths.memory_db, config=self.config)
            except PermissionError as exc:
                memory_store = None
                warnings.append(f"memory store unavailable: {exc}")
        skill_manager = self._provided_skill_manager
        if skill_manager is None and runtime is not None:
            skill_manager = getattr(runtime, "skill_manager", None)
        if skill_manager is None and memory_store is not None:
            try:
                skill_manager = SkillManager(config=self.config, memory_store=memory_store)
            except PermissionError as exc:
                skill_manager = None
                warnings.append(f"skill manager unavailable: {exc}")
        tool_registry = self._provided_tool_registry or getattr(runtime, "tool_registry", None) or ToolRegistry(self.config)
        memory_agent = getattr(runtime, "memory_agent", None) if runtime is not None else None
        if memory_agent is None and memory_store is not None and skill_manager is not None:
            try:
                memory_agent = MemoryAgent(
                    config=self.config,
                    memory_store=memory_store,
                    skill_manager=skill_manager,
                    trace=trace,
                )
            except PermissionError as exc:
                warnings.append(f"memory agent unavailable: {exc}")
        ui_agent = getattr(runtime, "ui_agent", None) if runtime is not None else None
        if ui_agent is None:
            ui_agent = UIAgent(config=self.config, model_router=model_router, trace=trace)
        for warning in warnings:
            trace.add_step("AgentLoop", "warning", warning)
        return AgentLoopServices(
            config=self.config,
            model_router=model_router,
            memory_store=memory_store,
            skill_manager=skill_manager,
            tool_registry=tool_registry,
            warnings=warnings,
            memory_agent=memory_agent,
            ui_agent=ui_agent,
            agent_runtime=runtime,
        )

    def run(self, request: AgentMessage, trace: RequestTrace | None = None) -> dict[str, Any]:
        active_trace = trace or TRACE_STORE.start_trace(request.content)
        active_trace.user_input = request.content
        coordinator = CoordinatorAgent(config=self.config, trace=active_trace)
        coordinator.record("received", "agent loop request received", {"message": request.to_dict()})
        started = time.time()
        services = self._services(active_trace)
        if services.agent_runtime is not None:
            services.agent_runtime.record_agent_boundary("CoordinatorAgent", "start", "coordinator starting task")
        context = self._assemble_context(request, services, active_trace)
        active_trace.add_step("AgentLoop", "context", "assembled planning context", {
            "skills": len(context.get("skills", [])),
            "memory_rows": len(context.get("recent_memory", [])),
        })

        try:
            plan = self._plan(request, context, services, active_trace)
        except Exception as exc:
            return self._error_response(request, active_trace, "planning_failed", str(exc), started, services.warnings)

        tool_results = self._execute_plan(request, plan, services, active_trace)
        summary = self._summarize(request, plan, tool_results, services, active_trace)
        memory_result = self._save_conversation(request, plan, tool_results, summary, services, active_trace)
        draft_result = self._maybe_create_auto_skill(request, plan, tool_results, services, active_trace)

        status = "ok"
        if any(item["status"] == "blocked" for item in tool_results):
            status = "blocked"
        elif any(item["status"] == "needs_confirmation" for item in tool_results):
            status = "needs_confirmation"
        elif any(item["status"] in {"error", "timeout"} for item in tool_results):
            status = "error"

        response = {
            "status": status,
            "summary": summary["user_summary"],
            "internal_summary": summary["memory_summary"],
            "plan": plan,
            "steps": tool_results,
            "memory": memory_result,
            "auto_skill": draft_result,
            "warnings": list(services.warnings),
            "trace_id": active_trace.request_id,
            "trace": active_trace.to_dict(),
            "duration_ms": round((time.time() - started) * 1000.0, 3),
        }
        if services.ui_agent is not None:
            shaped = services.ui_agent.shape_response(
                response,
                user_text=request.content,
                user_profile=context.get("user_profile", {}),
            )
            response.update(shaped)
        active_trace.add_step("AgentLoop", "completed", "agent loop completed", {"status": status})
        response["trace"] = active_trace.to_dict()
        self._persist_trace(active_trace, response)
        return response

    def _assemble_context(
        self,
        request: AgentMessage,
        services: AgentLoopServices,
        trace: RequestTrace,
    ) -> dict[str, Any]:
        if services.memory_agent is not None:
            bundle = services.memory_agent.get_context_bundle(
                request.content,
                dict(request.metadata.get("context") or {}),
            )
            profile = bundle.get("user_profile", {})
            recent_memory = bundle.get("recent_tasks", [])
            skills = bundle.get("relevant_skills", [])
        else:
            profile: dict[str, Any] = {}
            recent_memory: list[dict[str, Any]] = []
            if services.memory_store is not None:
                profile = services.memory_store.get_user_profile()
                recent_memory = services.memory_store.search_memory(
                    "conversation",
                    request.content or "task",
                    limit=5,
                    trace=trace,
                )
            skills: list[dict[str, Any]] = []
            if services.skill_manager is not None:
                skills = services.skill_manager.list_skills(query=request.content, register=True)
                if not skills:
                    skills = services.skill_manager.list_skills(register=True)[:5]
        os_context = {
            "system": platform.system(),
            "release": platform.release(),
            "cwd": request.metadata.get("context", {}).get("cwd") or ".",
        }
        return {
            "user_text": request.content,
            "request_metadata": dict(request.metadata),
            "user_profile": profile,
            "recent_memory": recent_memory,
            "skills": skills,
            "os_context": os_context,
            "risk_policy": {
                "levels": ["SAFE", "ASK", "BLOCK"],
                "ask_requires": "auto_approve_ask=true or explicit user approval",
            },
        }

    def _planning_prompt(self, context: dict[str, Any]) -> str:
        return (
            "You are ShellAI CoordinatorAgent. Return only JSON matching this schema:\n"
            "{\n"
            '  "schema_version": "1.0",\n'
            '  "user_message": "short note",\n'
            '  "skills": ["optional skill ids"],\n'
            '  "mark_reusable": false,\n'
            '  "steps": [\n'
            '    {"id":"step_1","tool":"shell|file|os","description":"...","args":{},"dry_run":false}\n'
            "  ]\n"
            "}\n"
            "Use shell commands and code in English. Explanations may match the user's language style.\n"
            f"Context:\n{_safe_preview(context, 8000)}"
        )

    def _plan(
        self,
        request: AgentMessage,
        context: dict[str, Any],
        services: AgentLoopServices,
        trace: RequestTrace,
    ) -> dict[str, Any]:
        explicit_command = _explicit_shell_command(request.content)
        if explicit_command:
            plan = _deterministic_shell_plan(explicit_command)
            trace.add_step("ModelRouter", "skipped", "explicit shell command used deterministic plan")
            return plan

        prompt = self._planning_prompt(context)
        trace.add_step("ModelRouter", "start", "requesting planning model", {"model_role": "planning"})
        response = services.model_router.complete(prompt, model_role="planning")
        plan = _validate_plan(_extract_json_object(response.text))
        trace.add_step("ModelRouter", "ok", "planning model returned valid plan", {"steps": len(plan["steps"])})
        return plan

    def _execute_plan(
        self,
        request: AgentMessage,
        plan: dict[str, Any],
        services: AgentLoopServices,
        trace: RequestTrace,
    ) -> list[dict[str, Any]]:
        context = dict(request.metadata.get("context") or {})
        working_dir = context.get("cwd")
        auto_approve = bool(request.metadata.get("auto_approve_ask", False))
        results: list[dict[str, Any]] = []
        for step in plan["steps"]:
            tool = services.tool_registry.get_tool(step["tool"])
            tool_request = ToolRequest(
                tool_name=step["tool"],
                args=dict(step["args"]),
                working_dir=working_dir,
                trace=trace,
                dry_run=bool(step.get("dry_run", False)),
                approved=auto_approve,
            )
            trace.add_step("AgentLoop", "tool_start", step["description"], {"tool": step["tool"], "step_id": step["id"]})
            result: ToolResult = tool.run(tool_request)
            results.append({
                "id": step["id"],
                "description": step["description"],
                "tool": step["tool"],
                "status": result.status,
                "stdout": result.stdout[:4000],
                "stderr": result.stderr[:2000],
                "exit_code": result.exit_code,
                "metadata": result.metadata,
                "duration_ms": result.duration_ms,
            })
        return results

    def _summarize(
        self,
        request: AgentMessage,
        plan: dict[str, Any],
        tool_results: list[dict[str, Any]],
        services: AgentLoopServices,
        trace: RequestTrace,
    ) -> dict[str, str]:
        payload = {
            "task": request.content,
            "plan_user_message": plan.get("user_message", ""),
            "steps": [
                {
                    "tool": item["tool"],
                    "status": item["status"],
                    "stderr": item.get("stderr", "")[:300],
                    "stdout": item.get("stdout", "")[:300],
                }
                for item in tool_results
            ],
        }
        fallback_user = self._fallback_summary(payload)
        fallback_memory = f"Task: {request.content}; outcome: {payload['steps']}"
        try:
            trace.add_step("ModelRouter", "start", "requesting summarization model", {"model_role": "summarization"})
            response = services.model_router.complete(
                "Return JSON with user_summary and memory_summary for this ShellAI task:\n"
                + _safe_preview(payload, 6000),
                model_role="summarization",
            )
            data = _extract_json_object(response.text)
            user_summary = str(data.get("user_summary") or fallback_user)
            memory_summary = str(data.get("memory_summary") or fallback_memory)
            trace.add_step("ModelRouter", "ok", "summarization model returned summary")
            return {"user_summary": user_summary, "memory_summary": memory_summary}
        except Exception as exc:
            trace.add_step("ModelRouter", "fallback", "summarization fallback used", {"error": str(exc)})
            return {"user_summary": fallback_user, "memory_summary": fallback_memory}

    @staticmethod
    def _fallback_summary(payload: dict[str, Any]) -> str:
        steps = payload.get("steps") or []
        if not steps:
            return "No steps were executed."
        statuses = ", ".join(f"{step['tool']}={step['status']}" for step in steps)
        return f"Completed task with step statuses: {statuses}."

    def _save_conversation(
        self,
        request: AgentMessage,
        plan: dict[str, Any],
        tool_results: list[dict[str, Any]],
        summary: dict[str, str],
        services: AgentLoopServices,
        trace: RequestTrace,
    ) -> dict[str, Any] | None:
        if services.memory_store is None:
            return None
        if services.memory_agent is not None:
            return services.memory_agent.save_task_result(
                {
                    "conversation_id": request.metadata.get("conversation_id") or trace.request_id,
                    "agent_role": AgentRole.COORDINATOR,
                    "user_input": request.content,
                    "plan": plan,
                },
                tool_results,
                summary,
                "recorded",
            )
        return services.memory_store.save_memory(
            "conversation",
            {
                "conversation_id": request.metadata.get("conversation_id") or trace.request_id,
                "agent_role": AgentRole.COORDINATOR,
                "user_input": request.content,
                "agent_output": summary["user_summary"],
                "summary": summary["memory_summary"],
                "metadata": {
                    "plan": plan,
                    "steps": tool_results,
                    "status": "recorded",
                },
            },
            trace=trace,
        )

    def _maybe_create_auto_skill(
        self,
        request: AgentMessage,
        plan: dict[str, Any],
        tool_results: list[dict[str, Any]],
        services: AgentLoopServices,
        trace: RequestTrace,
    ) -> dict[str, Any] | None:
        if services.skill_manager is None:
            return None
        shell_commands = [
            str(item.get("metadata", {}).get("command") or "")
            for item in tool_results
            if item.get("tool") == "shell" and item.get("status") == "ok"
        ]
        shell_commands = [command for command in shell_commands if command]
        reusable = bool(plan.get("mark_reusable")) or len(shell_commands) > 1
        if not reusable:
            return None
        try:
            skill = services.skill_manager.create_auto_skill_draft(
                task_description=request.content,
                commands=shell_commands,
                final_summary=f"Reusable workflow from task: {request.content}",
                trace=trace,
            )
            return {"id": skill.id, "name": skill.name, "tags": skill.tags}
        except Exception as exc:
            trace.add_step("SkillManager", "error", "auto-skill draft failed", {"error": str(exc)})
            return {"error": str(exc)}

    def _error_response(
        self,
        request: AgentMessage,
        trace: RequestTrace,
        code: str,
        message: str,
        started: float,
        warnings: list[str],
    ) -> dict[str, Any]:
        trace.add_step("AgentLoop", "error", message, {"code": code})
        response = {
            "status": "error",
            "error": {"code": code, "message": message},
            "summary": f"Task failed during {code}: {message}",
            "steps": [],
            "warnings": list(warnings),
            "trace_id": trace.request_id,
            "trace": trace.to_dict(),
            "duration_ms": round((time.time() - started) * 1000.0, 3),
        }
        self._persist_trace(trace, response)
        response["trace"] = trace.to_dict()
        return response

    def _persist_trace(self, trace: RequestTrace, response: dict[str, Any]) -> None:
        try:
            record_trace_snapshot(
                self.config,
                trace,
                status=str(response.get("status") or "unknown"),
                summary=str(response.get("summary") or response.get("message") or ""),
                metadata={"steps": response.get("steps", [])},
            )
        except Exception as exc:
            trace.add_step("Monitor", "error", "failed to persist trace snapshot", {"error": str(exc)})


def run_agent_task(
    request: AgentMessage,
    trace: RequestTrace | None = None,
    *,
    config: ShellAIConfig | None = None,
    model_router: Any | None = None,
    memory_store: MemoryStore | None = None,
    skill_manager: SkillManager | None = None,
    tool_registry: ToolRegistry | None = None,
    agent_runtime: Any | None = None,
) -> dict[str, Any]:
    loop = AgentLoop(
        config=config,
        model_router=model_router,
        memory_store=memory_store,
        skill_manager=skill_manager,
        tool_registry=tool_registry,
        agent_runtime=agent_runtime,
    )
    return loop.run(request, trace=trace)


__all__ = [
    "AgentLoop",
    "AgentLoopServices",
    "AgentPlanError",
    "PLAN_SCHEMA_VERSION",
    "create_user_request",
    "run_agent_task",
]
