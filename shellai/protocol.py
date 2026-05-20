from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AgentRole(str, Enum):
    COORDINATOR = "CoordinatorAgent"
    SHELL = "ShellAgent"
    SAFETY = "SafetyAgent"
    MEMORY = "MemoryAgent"
    OPTIMIZER = "OptimizerAgent"
    UI = "UIAgent"

    @classmethod
    def normalize(cls, value: "AgentRole | str") -> str:
        if isinstance(value, cls):
            return value.value
        text = str(value or "").strip()
        for role in cls:
            if text == role.value or text.lower() == role.name.lower():
                return role.value
        return text


class MessageKind(str, Enum):
    USER_REQUEST = "user_request"
    REQUEST = "request"
    PLAN = "plan"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    POLICY_DECISION = "policy_decision"
    SUMMARY = "summary"
    ERROR = "error"


@dataclass(frozen=True)
class AgentMessage:
    sender: str
    recipient: str
    kind: MessageKind
    content: str
    trace_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    message_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    created_at: float = field(default_factory=time.time)

    @classmethod
    def create(
        cls,
        *,
        sender: AgentRole | str,
        recipient: AgentRole | str,
        kind: MessageKind | str,
        content: str,
        trace_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> "AgentMessage":
        resolved_kind = kind if isinstance(kind, MessageKind) else MessageKind(str(kind))
        return cls(
            sender=AgentRole.normalize(sender),
            recipient=AgentRole.normalize(recipient),
            kind=resolved_kind,
            content=str(content or ""),
            trace_id=str(trace_id or ""),
            metadata=dict(metadata or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "sender": self.sender,
            "recipient": self.recipient,
            "kind": self.kind.value,
            "content": self.content,
            "trace_id": self.trace_id,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
        }


__all__ = ["AgentMessage", "AgentRole", "MessageKind"]
