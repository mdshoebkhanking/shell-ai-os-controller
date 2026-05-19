from __future__ import annotations

import os
import platform
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.events import AIEventType, publish_event


ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class PlatformDomainStatus:
    name: str
    status: str
    score: int
    summary: str
    metrics: dict[str, Any] = field(default_factory=dict)
    signals: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status in {"ready", "optimal"}

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "ok": self.ok,
            "score": int(self.score),
            "summary": self.summary,
            "metrics": dict(self.metrics),
            "signals": list(self.signals),
            "risks": list(self.risks),
            "next_actions": list(self.next_actions),
        }


@dataclass(frozen=True)
class PlatformSnapshot:
    generated_at: float
    version: str
    profile: str
    score: int
    status: str
    domains: list[PlatformDomainStatus]
    recommendations: list[str]
    latency_budget_ms: dict[str, float]
    process: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "version": self.version,
            "profile": self.profile,
            "score": int(self.score),
            "status": self.status,
            "domains": [domain.to_dict() for domain in self.domains],
            "recommendations": list(self.recommendations),
            "latency_budget_ms": dict(self.latency_budget_ms),
            "process": dict(self.process),
        }


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _bounded_score(raw: int) -> int:
    return max(0, min(100, int(raw)))


class ShellPlatformSupervisor:
    """Read-only AI OS control plane for runtime readiness.

    The supervisor deliberately samples public status surfaces instead of
    importing heavyweight providers or reading secrets. It is safe to expose in
    chat/UI because API keys are reduced to configured/missing states.
    """

    LATENCY_BUDGET_MS = {
        "ui_reaction": 50.0,
        "first_visible_token": 250.0,
        "turn_cancel": 25.0,
        "sse_transport_overhead": 50.0,
        "premium_first_audible_target": 1200.0,
    }

    def snapshot(self, *, include_catalog: bool = True, deep_packaging: bool = False) -> PlatformSnapshot:
        started = time.perf_counter()
        domains = [
            self._realtime_domain(),
            self._voice_domain(),
            self._agent_domain(),
            self._memory_domain(),
            self._multimodal_domain(),
            self._packaging_domain(deep=deep_packaging),
            self._hybrid_domain(),
        ]
        if include_catalog:
            domains.append(self._capability_domain())

        score = _bounded_score(round(sum(domain.score for domain in domains) / max(1, len(domains))))
        status = "optimal" if score >= 92 else "ready" if score >= 80 else "attention" if score >= 60 else "blocked"
        snapshot = PlatformSnapshot(
            generated_at=time.time(),
            version=self._version(),
            profile="realtime_ai_os",
            score=score,
            status=status,
            domains=domains,
            recommendations=self._recommendations(domains),
            latency_budget_ms=dict(self.LATENCY_BUDGET_MS),
            process={
                "platform": platform.system(),
                "release": platform.release(),
                "python": platform.python_version(),
                "snapshot_ms": round((time.perf_counter() - started) * 1000.0, 3),
                "cwd": str(ROOT),
            },
        )
        try:
            publish_event(
                AIEventType.OPS_CENTER_SNAPSHOT_CREATED,
                {"score": snapshot.score, "status": snapshot.status, "domains": [d.name for d in domains]},
                source="core.platform_supervisor",
            )
        except Exception:
            pass
        return snapshot

    def _version(self) -> str:
        try:
            from shell_prompts import APP_VERSION

            return str(APP_VERSION)
        except Exception:
            version_path = ROOT / "VERSION"
            try:
                return version_path.read_text(encoding="utf-8").strip()
            except Exception:
                return "unknown"

    def _realtime_domain(self) -> PlatformDomainStatus:
        metrics: dict[str, Any] = {
            "shell_v2_stream_default": _truthy(os.environ.get("SHELL_V2_STREAM_DEFAULT", "1")),
            "shell_v2_timeout_s": float(os.environ.get("SHELL_V2_TIMEOUT_S", "1") or 1),
            "predictive_prewarm": _truthy(os.environ.get("SHELL_VOICE_INTENT_PREWARM", "1")),
            "semantic_pacing": _truthy(os.environ.get("SHELL_SEMANTIC_PACING", "1")),
        }
        signals = ["low-overhead SSE path available", "interruption-first cancellation probes exist"]
        risks: list[str] = []
        if metrics["shell_v2_timeout_s"] > 2.0:
            risks.append("Shell-v2 timeout is above the realtime target")
        try:
            from shell_realtime_voice_session import RealtimeVoiceSession

            started = time.perf_counter()
            session = RealtimeVoiceSession(session_id="platform-supervisor")
            session.start()
            prewarm_before = session.should_prewarm()
            session.prewarm_started()
            session.prewarm_done(elapsed_ms=2.5, shell_v2_ready=True, provider_count=7)
            session.interrupt("platform_probe")
            metrics["session_control_overhead_ms"] = round((time.perf_counter() - started) * 1000.0, 3)
            metrics["prewarm_before_first_turn"] = bool(prewarm_before)
            metrics["interruption_count"] = session.snapshot()["interruption_count"]
        except Exception as exc:
            risks.append(f"realtime session probe unavailable: {type(exc).__name__}")
        score = 94 - (8 if risks else 0)
        return PlatformDomainStatus(
            "realtime",
            "ready" if not risks else "attention",
            score,
            "Persistent realtime session control, SSE streaming, and cancellation surfaces are available.",
            metrics,
            signals,
            risks,
            ["Promote provider-native duplex sessions when the voice transport is stable."],
        )

    def _voice_domain(self) -> PlatformDomainStatus:
        metrics: dict[str, Any] = {}
        risks: list[str] = []
        signals: list[str] = []
        try:
            from shell_voice_runtime import TTSSpeaker

            identity = TTSSpeaker().voice_identity_snapshot()
            metrics.update(identity)
            if identity.get("gemini_voice") == "Aoede":
                signals.append("premium Aoede identity selected")
            else:
                risks.append("premium Aoede identity is not the active Gemini voice")
            if identity.get("premium_voice_first"):
                signals.append("premium voice-first routing enabled")
            else:
                risks.append("premium voice-first routing is disabled")
            if identity.get("premium_streaming_voice"):
                signals.append("Gemini Live streaming voice path enabled")
            else:
                risks.append("premium streaming voice path is disabled")
            if identity.get("cloud_fallback_allowed"):
                risks.append("system/local voice fallback may replace premium identity")
        except Exception as exc:
            risks.append(f"voice identity probe unavailable: {type(exc).__name__}")
        score = 96 - (10 * len(risks))
        return PlatformDomainStatus(
            "voice",
            "ready" if not risks else "attention",
            score,
            "Premium voice identity and realtime-safe voice routing are observable.",
            metrics,
            signals,
            risks,
            ["Keep measuring real first-audible latency and migrate premium speech to provider-native streaming where possible."],
        )

    def _agent_domain(self) -> PlatformDomainStatus:
        metrics: dict[str, Any] = {}
        risks: list[str] = []
        signals: list[str] = []
        try:
            from core.agent_orchestrator import AgentFirstOrchestrator

            orchestrator = AgentFirstOrchestrator()
            agents = orchestrator.agents()
            math_plan = orchestrator.orchestrate("what is 2 + 3 * 4").to_dict()
            risky_plan = orchestrator.orchestrate("terminal echo hello").to_dict()
            metrics = {
                "agent_count": len(agents),
                "sample_agent": math_plan.get("selected_agent_id"),
                "sample_capability": math_plan.get("capability"),
                "risky_terminal_blocked": risky_plan.get("requires_approval") is True and risky_plan.get("execution_allowed") is False,
                "risky_agent": risky_plan.get("selected_agent_id"),
            }
            signals.append("tools are routed as internal agent capabilities")
            if not metrics["risky_terminal_blocked"]:
                risks.append("risky terminal capability was not blocked by agent policy")
        except Exception as exc:
            risks.append(f"agent supervisor probe unavailable: {type(exc).__name__}")
        score = 93 - (15 if risks else 0)
        return PlatformDomainStatus(
            "agents",
            "ready" if not risks else "attention",
            score,
            "Agent-first orchestration is active with bounded specialist agents and approval gates.",
            metrics,
            signals,
            risks,
            ["Add validator-agent result checks for multi-step workflow execution."],
        )

    def _memory_domain(self) -> PlatformDomainStatus:
        risks: list[str] = []
        metrics: dict[str, Any] = {}
        signals: list[str] = []
        try:
            from core.memory import LocalMemoryStore, MemoryFabric

            store = LocalMemoryStore(ROOT / ".shell_memory_store.json")
            data = store._load()
            records = data.get("records", []) if isinstance(data, dict) else []
            namespaces = sorted({str(row.get("namespace") or "") for row in records if isinstance(row, dict)})
            metrics = {
                "store_path": ".shell_memory_store.json",
                "record_count": len(records),
                "namespaces": namespaces[:12],
                "fabric_layers": sorted(MemoryFabric.LAYERS.keys()),
            }
            signals.append("local-first semantic/workflow memory fabric available")
            if not (ROOT / ".shell_memory_store.json").exists():
                risks.append("memory store has not been hydrated yet")
        except Exception as exc:
            risks.append(f"memory probe unavailable: {type(exc).__name__}")
        score = 84 if risks else 91
        return PlatformDomainStatus(
            "memory",
            "ready" if not risks else "attention",
            score,
            "Local memory primitives exist for conversation, workflow, semantic, and failure recall.",
            metrics,
            signals,
            risks,
            ["Bind agent plans to scoped memory writes after validated executions."],
        )

    def _multimodal_domain(self) -> PlatformDomainStatus:
        expected = {
            "screen": ROOT / "shell_screen_vision.py",
            "ocr": ROOT / "shell_ocr.py",
            "screenshot": ROOT / "shell_screenshot.py",
            "multimodal_core": ROOT / "core" / "multimodal",
            "vision_core": ROOT / "core" / "vision",
        }
        available = {name: path.exists() for name, path in expected.items()}
        risks = [f"{name} surface missing" for name, ok in available.items() if not ok]
        return PlatformDomainStatus(
            "multimodal",
            "ready" if not risks else "attention",
            88 if not risks else 72,
            "Screen, OCR, screenshot, and multimodal extension surfaces are present.",
            {"available": available},
            ["desktop awareness primitives are present"],
            risks,
            ["Unify screen/OCR/image observations into the agent context fabric."],
        )

    def _packaging_domain(self, *, deep: bool = False) -> PlatformDomainStatus:
        risks: list[str] = []
        metrics: dict[str, Any] = {}
        if deep:
            try:
                from tools.production_release_check import build_report

                report = build_report(include_health=False, strict=False)
                blockers = list(report.get("blockers") or [])
                warnings = list(report.get("warnings") or [])
                metrics = {
                    "release_status": report.get("status"),
                    "blocker_count": len(blockers),
                    "warning_count": len(warnings),
                    "health": "skipped",
                    "mode": "deep_release_guard",
                }
                risks.extend(str(item)[:180] for item in blockers)
            except Exception as exc:
                risks.append(f"release packaging probe unavailable: {type(exc).__name__}")
        else:
            required = [
                "README.md",
                "INSTALLATION.md",
                "requirements.txt",
                "installer/bootstrap.py",
                "launch.py",
                "shell_hub.py",
                "Start_ShellAI.bat",
                "start_shellai.sh",
            ]
            missing = [name for name in required if not (ROOT / name).exists()]
            metrics = {
                "mode": "fast_asset_guard",
                "required_assets": len(required),
                "missing_assets": missing,
                "local_env_present": (ROOT / ".env").exists(),
                "deep_release_guard_available": (ROOT / "tools" / "production_release_check.py").exists(),
            }
            risks.extend(f"release asset missing: {name}" for name in missing)
        score = 92 if not risks else 65
        return PlatformDomainStatus(
            "packaging",
            "ready" if not risks else "blocked",
            score,
            "Installer and public release guardrails are callable without exposing local secrets.",
            metrics,
            ["public release guard can run in non-strict mode"],
            risks,
            ["Run strict release guard only when preparing a public package."],
        )

    def _hybrid_domain(self) -> PlatformDomainStatus:
        tools = {
            "rustc": shutil.which("rustc") is not None,
            "cargo": shutil.which("cargo") is not None,
            "go": shutil.which("go") is not None,
            "node": shutil.which("node") is not None,
            "npm": shutil.which("npm") is not None,
        }
        runtime_targets = [
            "Rust/Tokio runtime core for websocket, IPC, and audio scheduling",
            "Python AI workers for provider SDKs and orchestration iteration",
            "Tauri shell when native packaging replaces the current PyQt shell",
        ]
        risks = []
        if not tools["rustc"] or not tools["cargo"]:
            risks.append("Rust toolchain is not available for future runtime-core extraction")
        if not tools["go"]:
            risks.append("Go toolchain is not available for future network-service prototypes")
        score = 82 if risks else 90
        return PlatformDomainStatus(
            "hybrid_runtime",
            "attention" if risks else "ready",
            score,
            "Hybrid migration plan is explicit while Python remains the AI integration layer.",
            {"toolchains": tools, "runtime_targets": runtime_targets},
            ["safe extraction candidates identified"],
            risks,
            ["Prototype only one measured low-level bottleneck before any Rust/Go migration."],
        )

    def _capability_domain(self) -> PlatformDomainStatus:
        risks: list[str] = []
        metrics: dict[str, Any] = {}
        try:
            from shell_tool_catalog import discover_capabilities

            catalog = discover_capabilities().get("catalog", [])
            by_kind: dict[str, int] = {}
            by_category: dict[str, int] = {}
            readiness = {"ready": 0, "not_ready": 0}
            for row in catalog:
                by_kind[str(row.get("kind") or "tool")] = by_kind.get(str(row.get("kind") or "tool"), 0) + 1
                by_category[str(row.get("category") or "general")] = by_category.get(str(row.get("category") or "general"), 0) + 1
                ready = row.get("readiness", {})
                if isinstance(ready, dict) and ready.get("ok") is False:
                    readiness["not_ready"] += 1
                else:
                    readiness["ready"] += 1
            metrics = {
                "total": len(catalog),
                "by_kind": by_kind,
                "top_categories": dict(sorted(by_category.items(), key=lambda item: item[1], reverse=True)[:8]),
                "readiness": readiness,
            }
            if len(catalog) <= 0:
                risks.append("capability catalog is empty")
        except Exception as exc:
            risks.append(f"capability catalog probe unavailable: {type(exc).__name__}")
        return PlatformDomainStatus(
            "capabilities",
            "ready" if not risks else "attention",
            90 if not risks else 60,
            "Tool catalog remains available as the low-level capability layer under agents.",
            metrics,
            ["capabilities are internally discoverable"],
            risks,
            ["Continue migrating user-facing intents from direct tool calls to agent routes."],
        )

    def _recommendations(self, domains: list[PlatformDomainStatus]) -> list[str]:
        recommendations: list[str] = []
        for domain in domains:
            if domain.status != "ready" and domain.next_actions:
                recommendations.append(f"{domain.name}: {domain.next_actions[0]}")
        recommendations.extend([
            "Keep premium voice identity and real first-audible telemetry as release gates.",
            "Make realtime session state visible in UI diagnostics before adding duplex provider sessions.",
            "Treat Rust/Go migration as bottleneck-led extraction, not a rewrite.",
        ])
        return recommendations[:8]


def build_platform_snapshot(*, include_catalog: bool = True, deep_packaging: bool = False) -> dict[str, Any]:
    return ShellPlatformSupervisor().snapshot(
        include_catalog=include_catalog,
        deep_packaging=deep_packaging,
    ).to_dict()
