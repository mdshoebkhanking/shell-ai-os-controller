from __future__ import annotations

import json
import os
import platform
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .protocol import AgentRole


def default_config_path() -> Path:
    configured = os.environ.get("SHELLAI_CONFIG")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".shellai" / "config.json"


DEFAULT_RISK_POLICY: dict[str, Any] = {
    "default": "ASK",
    "safe_patterns": [
        r"^\s*(pwd|whoami|date|uname(\s+-a)?|hostname)\s*$",
        r"^\s*(ls|dir)(\s+[-\w./~ ]*)?$",
        r"^\s*git\s+status(\s+[-\w./~ ]*)?$",
        r"^\s*(python|python3|node|npm|pip)\s+--version\s*$",
    ],
    "ask_patterns": [
        r"\bsudo\b",
        r"\brm\b",
        r"\bmv\b",
        r"\bchmod\b",
        r"\bchown\b",
        r"\bkill(all)?\b",
        r"\bpkill\b",
        r"\bpip\s+install\b",
        r"\bnpm\s+install\b",
        r"\bgit\s+push\b",
        r"\bdocker\s+system\s+prune\b",
        r"\bcurl\b.*\|\s*(sh|bash|zsh)\b",
    ],
    "block_patterns": [
        r"\brm\s+(-\w*\s+)*-rf\s+/\s*$",
        r"\brm\s+(-\w*\s+)*-rf\s+/\*",
        r"\brm\s+(-\w*\s+)*-rf\s+~",
        r"\bsudo\s+rm\s+(-\w*\s+)*-rf\s+/",
        r"\bmkfs\b",
        r"\bdd\b.*\bof=/dev/",
        r"\bdiskutil\s+eraseDisk\b",
        r"\bformat\s+[a-zA-Z]:",
        r"\bshutdown\b",
        r"\breboot\b",
        r"\bhalt\b",
        r":\(\)\{\s*:\|:&\s*\};:",
    ],
}


DEFAULT_ENABLED_TOOLS: dict[str, bool] = {
    "shell": True,
    "file": True,
    "git": True,
    "python": True,
    "node": True,
    "browser": True,
    "android_adb": False,
    "vscode": False,
    "os": False,
}


DEFAULT_USER_PROFILE: dict[str, Any] = {
    "primary_user": "power-user developer in India",
    "regions": ["Latur", "Mumbai"],
    "language_style": "mixed Hindi + English, with Marathi/Urdu support",
    "preferred_explanation_style": "match the user's language mix; keep commands and code in English",
    "high_priority_tools": ["git", "python", "node", "android_adb", "vscode", "browser"],
    "os_priority": ["linux", "windows", "macos_optional"],
}


DEFAULT_AGENT_MODEL_ROLES: dict[str, str] = {
    AgentRole.COORDINATOR.value: "planning",
    AgentRole.SHELL.value: "command",
    AgentRole.SAFETY.value: "command",
    AgentRole.MEMORY.value: "summarization",
    AgentRole.OPTIMIZER.value: "planning",
    AgentRole.UI.value: "command",
}


DEFAULT_PROVIDER_BACKENDS: dict[str, dict[str, Any]] = {
    "openai": {
        "kind": "openai_compatible",
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
        "default_model": "gpt-4o-mini",
        "enabled": True,
    },
    "openrouter": {
        "kind": "openai_compatible",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY",
        "default_model": "openai/gpt-4o-mini",
        "enabled": True,
    },
    "ollama": {
        "kind": "ollama",
        "base_url": "http://127.0.0.1:11434",
        "api_key_env": "",
        "default_model": "llama3.1",
        "enabled": True,
    },
}


def _env_first(*names: str) -> str:
    for name in names:
        value = os.environ.get(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _looks_configured_secret(value: str | None) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    low = text.lower()
    return not (
        low.startswith("your_")
        or low.startswith("replace_")
        or low in {"changeme", "change_me", "paste_key_here", "api_key", "token", "none", "null"}
    )


@dataclass(frozen=True)
class ShellAIPaths:
    home_dir: Path
    config_file: Path
    data_dir: Path
    logs_dir: Path
    memory_db: Path
    skills_dir: Path
    auto_skills_dir: Path
    traces_dir: Path

    @classmethod
    def from_config_path(cls, config_path: str | Path | None = None) -> "ShellAIPaths":
        config_file = Path(config_path).expanduser() if config_path else default_config_path()
        home_dir = config_file.parent
        data_dir = home_dir / "data"
        skills_dir = home_dir / "skills"
        return cls(
            home_dir=home_dir,
            config_file=config_file,
            data_dir=data_dir,
            logs_dir=home_dir / "logs",
            memory_db=data_dir / "memory.sqlite3",
            skills_dir=skills_dir,
            auto_skills_dir=skills_dir / "auto",
            traces_dir=home_dir / "traces",
        )

    def ensure_runtime_dirs(self) -> None:
        for path in (self.home_dir, self.data_dir, self.logs_dir, self.skills_dir, self.auto_skills_dir, self.traces_dir):
            path.mkdir(parents=True, exist_ok=True)

    def to_dict(self) -> dict[str, str]:
        return {
            "home_dir": str(self.home_dir),
            "config_file": str(self.config_file),
            "data_dir": str(self.data_dir),
            "logs_dir": str(self.logs_dir),
            "memory_db": str(self.memory_db),
            "skills_dir": str(self.skills_dir),
            "auto_skills_dir": str(self.auto_skills_dir),
            "traces_dir": str(self.traces_dir),
        }


@dataclass
class ModelRoleConfig:
    planning: str = "gpt-4o-mini"
    command: str = "gpt-4o-mini"
    summarization: str = "gpt-4o-mini"

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ModelRoleConfig":
        payload = dict(data or {})
        return cls(
            planning=str(payload.get("planning") or cls().planning),
            command=str(payload.get("command") or cls().command),
            summarization=str(payload.get("summarization") or cls().summarization),
        )

    def apply_env_overrides(self) -> None:
        planning = _env_first("SHELLAI_MODEL_PLANNING", "SHELLAI_PLANNING_MODEL")
        command = _env_first("SHELLAI_MODEL_COMMAND", "SHELLAI_COMMAND_MODEL")
        summarization = _env_first("SHELLAI_MODEL_SUMMARIZATION", "SHELLAI_SUMMARIZATION_MODEL")
        if planning:
            self.planning = planning
        if command:
            self.command = command
        if summarization:
            self.summarization = summarization

    def get(self, role: str) -> str:
        key = str(role or "").strip()
        if key not in {"planning", "command", "summarization"}:
            raise KeyError(f"Unknown model role: {role}")
        return str(getattr(self, key))

    def to_dict(self) -> dict[str, str]:
        return {
            "planning": self.planning,
            "command": self.command,
            "summarization": self.summarization,
        }


@dataclass
class ProviderBackendConfig:
    name: str
    kind: str = "openai_compatible"
    base_url: str = ""
    api_key_env: str = ""
    default_model: str = ""
    enabled: bool = True

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any] | None) -> "ProviderBackendConfig":
        defaults = dict(DEFAULT_PROVIDER_BACKENDS.get(name, {}))
        defaults.update(dict(data or {}))
        return cls(
            name=name,
            kind=str(defaults.get("kind") or "openai_compatible"),
            base_url=str(defaults.get("base_url") or ""),
            api_key_env=str(defaults.get("api_key_env") or ""),
            default_model=str(defaults.get("default_model") or ""),
            enabled=bool(defaults.get("enabled", True)),
        )

    @property
    def api_key_configured(self) -> bool:
        if not self.api_key_env:
            return True
        return _looks_configured_secret(os.environ.get(self.api_key_env))

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "base_url": self.base_url,
            "api_key_env": self.api_key_env,
            "default_model": self.default_model,
            "enabled": self.enabled,
        }

    def diagnostics(self) -> dict[str, Any]:
        data = self.to_dict()
        data["api_key_configured"] = self.api_key_configured
        return data


@dataclass
class ShellAIConfig:
    provider: str = "openai"
    models: ModelRoleConfig = field(default_factory=ModelRoleConfig)
    default_shell: str = field(default_factory=lambda: os.environ.get("SHELL") or platform.system().lower())
    enabled_tools: dict[str, bool] = field(default_factory=lambda: dict(DEFAULT_ENABLED_TOOLS))
    user_profile: dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_USER_PROFILE))
    providers: dict[str, ProviderBackendConfig] = field(default_factory=lambda: {
        name: ProviderBackendConfig.from_dict(name, None)
        for name in DEFAULT_PROVIDER_BACKENDS
    })
    agent_model_roles: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_AGENT_MODEL_ROLES))
    require_confirmation_for_ask: bool = True
    risk_policy: dict[str, Any] = field(default_factory=lambda: json.loads(json.dumps(DEFAULT_RISK_POLICY)))
    config_path: Path = field(default_factory=default_config_path)
    paths: ShellAIPaths = field(default_factory=ShellAIPaths.from_config_path)

    @classmethod
    def load(cls, path: str | Path | None = None) -> "ShellAIConfig":
        config_path = Path(path).expanduser() if path else default_config_path()
        data: dict[str, Any] = {}
        if config_path.exists():
            loaded = json.loads(config_path.read_text(encoding="utf-8"))
            if not isinstance(loaded, dict):
                raise ValueError(f"ShellAI config must be a JSON object: {config_path}")
            data = loaded
        if not isinstance(data, dict):
            raise ValueError(f"ShellAI config must be a JSON object: {config_path}")

        risk_policy = json.loads(json.dumps(DEFAULT_RISK_POLICY))
        risk_policy.update(dict(data.get("risk_policy") or {}))

        models = ModelRoleConfig.from_dict(data.get("models") if isinstance(data.get("models"), dict) else None)
        models.apply_env_overrides()

        provider_name = str(data.get("provider") or _env_first("SHELLAI_PROVIDER", "SHELL_AI_PROVIDER") or "openai")
        enabled_tools = dict(DEFAULT_ENABLED_TOOLS)
        enabled_tools.update(dict(data.get("enabled_tools") or {}))

        provider_payloads = dict(DEFAULT_PROVIDER_BACKENDS)
        for name, payload in dict(data.get("providers") or {}).items():
            merged = dict(provider_payloads.get(name, {}))
            merged.update(dict(payload or {}))
            provider_payloads[str(name)] = merged
        providers = {
            name: ProviderBackendConfig.from_dict(name, payload)
            for name, payload in provider_payloads.items()
        }

        agent_model_roles = dict(DEFAULT_AGENT_MODEL_ROLES)
        agent_model_roles.update(dict(data.get("agent_model_roles") or {}))
        config_paths = ShellAIPaths.from_config_path(config_path)
        return cls(
            provider=provider_name,
            models=models,
            default_shell=str(data.get("default_shell") or os.environ.get("SHELL") or platform.system().lower()),
            enabled_tools=enabled_tools,
            user_profile={**DEFAULT_USER_PROFILE, **dict(data.get("user_profile") or {})},
            providers=providers,
            agent_model_roles=agent_model_roles,
            require_confirmation_for_ask=bool(data.get("require_confirmation_for_ask", True)),
            risk_policy=risk_policy,
            config_path=config_path,
            paths=config_paths,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "models": self.models.to_dict(),
            "default_shell": self.default_shell,
            "enabled_tools": dict(self.enabled_tools),
            "user_profile": dict(self.user_profile),
            "providers": {
                name: provider.to_dict()
                for name, provider in sorted(self.providers.items())
            },
            "agent_model_roles": dict(self.agent_model_roles),
            "require_confirmation_for_ask": self.require_confirmation_for_ask,
            "risk_policy": dict(self.risk_policy),
        }

    def save(self) -> None:
        self.paths.ensure_runtime_dirs()
        tmp = self.config_path.with_suffix(self.config_path.suffix + ".tmp")
        tmp.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(self.config_path)

    def diagnostics(self) -> dict[str, Any]:
        return {
            **self.to_dict(),
            "config_path": str(self.config_path),
            "paths": self.paths.to_dict(),
            "active_provider": self.provider_config().diagnostics(),
        }

    def provider_config(self, provider: str | None = None) -> ProviderBackendConfig:
        name = str(provider or self.provider or "openai")
        if name in self.providers:
            return self.providers[name]
        return ProviderBackendConfig.from_dict(name, None)

    def model_for_role(self, role: str) -> str:
        return self.models.get(role)

    def model_for_agent(self, agent_name: str | AgentRole) -> str:
        name = AgentRole.normalize(agent_name)
        role_or_model = self.agent_model_roles.get(name, "planning")
        if role_or_model in {"planning", "command", "summarization"}:
            return self.model_for_role(role_or_model)
        return str(role_or_model)

    def set_value(self, dotted_key: str, value: str) -> None:
        key = str(dotted_key or "").strip()
        if key == "provider":
            self.provider = value
            return
        if key.startswith("models."):
            role = key.split(".", 1)[1]
            if role not in {"planning", "command", "summarization"}:
                raise KeyError(f"Unknown model role: {role}")
            setattr(self.models, role, value)
            return
        if key.startswith("enabled_tools."):
            tool = key.split(".", 1)[1]
            self.enabled_tools[tool] = str(value).strip().lower() in {"1", "true", "yes", "on", "enabled"}
            return
        if key.startswith("agent_model_roles."):
            agent = key.split(".", 1)[1]
            self.agent_model_roles[AgentRole.normalize(agent)] = value
            return
        if key.startswith("providers."):
            _prefix, provider, field_name = key.split(".", 2)
            current = self.provider_config(provider)
            payload = current.to_dict()
            if field_name == "enabled":
                payload[field_name] = str(value).strip().lower() in {"1", "true", "yes", "on", "enabled"}
            elif field_name in {"kind", "base_url", "api_key_env", "default_model"}:
                payload[field_name] = value
            else:
                raise KeyError(f"Unsupported provider config field: {field_name}")
            self.providers[provider] = ProviderBackendConfig.from_dict(provider, payload)
            return
        if key.startswith("user_profile."):
            profile_key = key.split(".", 1)[1]
            self.user_profile[profile_key] = value
            return
        raise KeyError(f"Unsupported config key: {dotted_key}")


__all__ = [
    "DEFAULT_AGENT_MODEL_ROLES",
    "DEFAULT_ENABLED_TOOLS",
    "DEFAULT_PROVIDER_BACKENDS",
    "DEFAULT_RISK_POLICY",
    "DEFAULT_USER_PROFILE",
    "ModelRoleConfig",
    "ProviderBackendConfig",
    "ShellAIConfig",
    "ShellAIPaths",
    "default_config_path",
]
