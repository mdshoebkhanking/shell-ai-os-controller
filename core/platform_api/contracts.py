from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from core.events.bus import AIEventType, publish_event


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class ApiScope(str, Enum):
    STATUS_READ = "status.read"
    SETTINGS_READ = "settings.read"
    SETTINGS_WRITE = "settings.write"
    SECRETS_WRITE = "secrets.write"
    VOICE_TOKEN = "voice.token"
    EVENTS_SUBSCRIBE = "events.subscribe"
    EVENTS_PUBLISH = "events.publish"
    TOOL_EXECUTE = "tool.execute"
    WORKFLOW_RUN = "workflow.run"
    MEMORY_READ = "memory.read"
    MEMORY_WRITE = "memory.write"
    CLOUD_SYNC = "cloud.sync"
    REMOTE_CONTROL = "remote.control"
    ADMIN = "admin"


@dataclass(frozen=True)
class ApiError:
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    retryable: bool = False
    status: int = 400

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "details": dict(self.details),
            "retryable": self.retryable,
            "status": self.status,
        }


@dataclass(frozen=True)
class ApiEnvelope:
    ok: bool
    request_id: str
    trace_id: str
    data: dict[str, Any] = field(default_factory=dict)
    error: ApiError | None = None
    warnings: list[str] = field(default_factory=list)

    @classmethod
    def success(
        cls,
        data: dict[str, Any] | None = None,
        *,
        request_id: str | None = None,
        trace_id: str = "",
        warnings: list[str] | None = None,
    ) -> "ApiEnvelope":
        return cls(
            ok=True,
            request_id=request_id or str(uuid4()),
            trace_id=trace_id,
            data=dict(data or {}),
            warnings=list(warnings or []),
        )

    @classmethod
    def failure(
        cls,
        error: ApiError,
        *,
        request_id: str | None = None,
        trace_id: str = "",
        warnings: list[str] | None = None,
    ) -> "ApiEnvelope":
        return cls(
            ok=False,
            request_id=request_id or str(uuid4()),
            trace_id=trace_id,
            error=error,
            warnings=list(warnings or []),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "request_id": self.request_id,
            "trace_id": self.trace_id,
            "data": dict(self.data),
            "error": self.error.to_dict() if self.error else None,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class ApiAuthContext:
    subject: str
    scopes: list[str]
    device_id: str = "local"
    token_id: str = ""
    expires_at: str = ""
    local_only: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def has_scopes(self, required: list[ApiScope | str]) -> bool:
        granted = set(self.scopes)
        if ApiScope.ADMIN.value in granted:
            return True
        return {scope.value if isinstance(scope, ApiScope) else str(scope) for scope in required}.issubset(granted)

    def to_dict(self, *, redact: bool = True) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "scopes": list(self.scopes),
            "device_id": self.device_id,
            "token_id": f"{self.token_id[:6]}..." if redact and self.token_id else self.token_id,
            "expires_at": self.expires_at,
            "local_only": self.local_only,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ApiRouteSpec:
    route_id: str
    method: str
    path: str
    scopes: list[ApiScope]
    local_only: bool = True
    rate_limit_per_min: int = 60
    streaming: bool = False
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "route_id": self.route_id,
            "method": self.method,
            "path": self.path,
            "scopes": [scope.value for scope in self.scopes],
            "local_only": self.local_only,
            "rate_limit_per_min": self.rate_limit_per_min,
            "streaming": self.streaming,
            "description": self.description,
        }


@dataclass(frozen=True)
class RealtimeEvent:
    type: str
    source: str
    data: dict[str, Any]
    subject: str = ""
    id: str = field(default_factory=lambda: str(uuid4()))
    time: str = field(default_factory=_utc_now)
    trace_id: str = ""
    specversion: str = "1.0"
    datacontenttype: str = "application/json"

    def to_cloudevent(self) -> dict[str, Any]:
        event = {
            "specversion": self.specversion,
            "type": self.type,
            "source": self.source,
            "id": self.id,
            "time": self.time,
            "datacontenttype": self.datacontenttype,
            "data": dict(self.data),
        }
        if self.subject:
            event["subject"] = self.subject
        if self.trace_id:
            event["trace_id"] = self.trace_id
        return event

    def validate(self) -> list[str]:
        problems: list[str] = []
        if self.specversion != "1.0":
            problems.append("CloudEvents specversion must be 1.0")
        if not self.type:
            problems.append("event type is required")
        if not self.source:
            problems.append("event source is required")
        if not self.id:
            problems.append("event id is required")
        return problems


class PlatformAPIContract:
    def __init__(self, routes: list[ApiRouteSpec] | None = None) -> None:
        self.routes = list(routes or self.default_routes())

    @staticmethod
    def default_routes() -> list[ApiRouteSpec]:
        return [
            ApiRouteSpec("ready.read", "GET", "/ready", [ApiScope.STATUS_READ], description="Fast local process readiness for launchers and acceptance probes."),
            ApiRouteSpec("health.read", "GET", "/health", [ApiScope.STATUS_READ], description="Runtime health and dependency status."),
            ApiRouteSpec("capabilities.read", "GET", "/capabilities", [ApiScope.STATUS_READ], description="Visible tool and runtime capability state."),
            ApiRouteSpec("token.voice", "GET", "/token", [ApiScope.VOICE_TOKEN], description="Ephemeral realtime voice/session token."),
            ApiRouteSpec("api_keys.list", "GET", "/api-keys", [ApiScope.SETTINGS_READ], description="List configured provider key names without secret values."),
            ApiRouteSpec("api_keys.save", "POST", "/api-keys", [ApiScope.SECRETS_WRITE], description="Save provider credentials through the settings backend."),
            ApiRouteSpec("api_keys.delete", "DELETE", "/api-keys/{provider}", [ApiScope.SECRETS_WRITE], description="Delete one provider credential."),
            ApiRouteSpec("settings.read", "GET", "/settings", [ApiScope.SETTINGS_READ], description="Read runtime settings."),
            ApiRouteSpec("settings.save", "POST", "/settings", [ApiScope.SETTINGS_WRITE], description="Persist runtime settings."),
            ApiRouteSpec("events.stream", "WS", "/socket.io", [ApiScope.EVENTS_SUBSCRIBE], streaming=True, description="Realtime UI, trace, and runtime state events."),
        ]

    def validate(self) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for route in self.routes:
            key = (route.method, route.path)
            if key in seen:
                findings.append({"severity": "high", "route": route.route_id, "message": "duplicate method/path route"})
            seen.add(key)
            if not route.route_id or not route.path or not route.method:
                findings.append({"severity": "high", "route": route.route_id, "message": "route id, method, and path are required"})
            if not route.scopes:
                findings.append({"severity": "medium", "route": route.route_id, "message": "route has no declared auth scopes"})
            if route.rate_limit_per_min <= 0:
                findings.append({"severity": "medium", "route": route.route_id, "message": "route has no usable rate limit"})
            if not route.local_only and route.scopes == [ApiScope.STATUS_READ]:
                findings.append({"severity": "medium", "route": route.route_id, "message": "remote routes should declare explicit external API policy"})
        publish_event(
            AIEventType.API_CONTRACT_VALIDATED,
            {"route_count": len(self.routes), "finding_count": len(findings)},
            source="core.platform_api",
        )
        return findings

    def authorize(self, route_id: str, auth: ApiAuthContext) -> ApiEnvelope:
        route = next((candidate for candidate in self.routes if candidate.route_id == route_id), None)
        if route is None:
            return ApiEnvelope.failure(ApiError("ROUTE_NOT_FOUND", f"Unknown route: {route_id}", status=404))
        allowed = auth.has_scopes(route.scopes)
        publish_event(
            AIEventType.API_AUTH_DECISION,
            {"route_id": route_id, "subject": auth.subject, "allowed": allowed, "required_scopes": [scope.value for scope in route.scopes]},
            source="core.platform_api",
        )
        if not allowed:
            return ApiEnvelope.failure(ApiError("FORBIDDEN", "Missing required API scope.", {"route_id": route_id}, status=403))
        return ApiEnvelope.success({"route_id": route_id, "allowed": True})

    def openapi_skeleton(self, *, title: str = "Shell AI OS Controller API", version: str = "1.0.0") -> dict[str, Any]:
        paths: dict[str, Any] = {}
        for route in self.routes:
            if route.method == "WS":
                paths.setdefault(route.path, {})["get"] = {
                    "summary": route.description,
                    "x-shell-realtime": True,
                    "x-required-scopes": [scope.value for scope in route.scopes],
                    "responses": {"101": {"description": "WebSocket upgrade via Socket.IO"}},
                }
                continue
            operation = {
                "operationId": route.route_id.replace(".", "_"),
                "summary": route.description,
                "x-local-only": route.local_only,
                "x-rate-limit-per-min": route.rate_limit_per_min,
                "security": [{"ShellBearer": [scope.value for scope in route.scopes]}],
                "responses": {
                    "200": {"description": "Successful Shell API envelope"},
                    "400": {"description": "Structured Shell API error envelope"},
                    "403": {"description": "Scope or policy denied"},
                },
            }
            paths.setdefault(route.path, {})[route.method.lower()] = operation
        return {
            "openapi": "3.1.0",
            "info": {"title": title, "version": version},
            "paths": paths,
            "components": {
                "securitySchemes": {
                    "ShellBearer": {
                        "type": "http",
                        "scheme": "bearer",
                        "bearerFormat": "opaque-local-token",
                    }
                }
            },
        }
