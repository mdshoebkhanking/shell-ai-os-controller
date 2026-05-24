"""
Swarm Base — Agent Foundation with Inter-Agent Messaging
==========================================================
Provides SwarmState (shared blackboard with messaging) and BaseAgent.
"""

import asyncio
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import logging

# Setup Logger
logger = logging.getLogger("swarm_core")


@dataclass
class SwarmState:
    """
    Shared Blackboard/Memory for the Swarm.
    Includes inter-agent messaging for agent-to-agent communication.
    """
    task_id: str
    original_request: str
    status: str = "pending"  # pending, in_progress, completed, failed
    plan: List[str] = field(default_factory=list)
    artifacts: Dict[str, Any] = field(default_factory=dict)
    history: List[Dict[str, str]] = field(default_factory=list)  # Chat history
    messages: List[Dict] = field(default_factory=list)  # Inter-agent messages

    def log(self, agent_name: str, message: str):
        """Log an event from an agent."""
        entry = f"[{datetime.now().strftime('%H:%M:%S')}] {agent_name}: {message}"
        self.history.append({
            "agent": agent_name,
            "message": message,
            "timestamp": str(datetime.now()),
        })
        logger.info(entry)

    def post_message(self, from_agent: str, to_agent: str, content: str):
        """
        Send a message from one agent to another via the shared state.
        Messages are stored until the recipient reads them.
        """
        self.messages.append({
            "from": from_agent,
            "to": to_agent,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "read": False,
        })

    def get_messages_for(self, agent_name: str) -> List[Dict]:
        """
        Retrieve all unread messages for a specific agent.
        Marks retrieved messages as read.
        """
        msgs = [m for m in self.messages if m["to"] == agent_name and not m["read"]]
        for m in msgs:
            m["read"] = True
        return msgs

    def get_all_messages(self) -> List[Dict]:
        """Return all messages (read and unread) for inspection."""
        return self.messages


class BaseAgent:
    """
    Abstract Base Agent using MultiAIBrain.
    All swarm agents inherit from this class.
    """

    def __init__(self, name: str, role: str, brain_core):
        self.name = name
        self.role = role
        self.brain = brain_core

    async def execute(self, task: str, state: SwarmState) -> str:
        """
        Main execution method to be overridden by subclasses.
        """
        raise NotImplementedError("Subclasses must implement execute()")

    _provider_unavailable_until = 0.0

    async def _generate_response(self, prompt: str, mode: str = "SMART", **kwargs) -> str:
        if time.time() < BaseAgent._provider_unavailable_until:
            return self._provider_unavailable_message()
        try:
            response = await self.brain.generate_response(prompt, mode=mode, **kwargs)
        except Exception as exc:
            BaseAgent._provider_unavailable_until = time.time() + 20.0
            logger.warning("%s brain call failed: %s", self.name, str(exc)[:300])
            return self._provider_unavailable_message()
        if self._is_provider_failure(response):
            BaseAgent._provider_unavailable_until = time.time() + 60.0
            logger.warning("%s provider chain unavailable: %s", self.name, str(response)[:300])
            return self._provider_unavailable_message()
        return response

    @staticmethod
    def _is_provider_failure(response: object) -> bool:
        text = str(response or "").lower()
        return (
            "all brains failed" in text
            or "api key missing" in text
            or "resource_exhausted" in text
            or "payment_method_required" in text
            or "rate limit reached" in text
        )

    def _provider_unavailable_message(self) -> str:
        return (
            f"AI providers are temporarily unavailable. {self.name} is loaded, "
            "but swarm model reasoning is in degraded mode. Check API keys/quota "
            "or retry after the provider cooldown."
        )

    def _format_context(self, state: SwarmState) -> str:
        """
        Creates a context string from the shared state for prompt injection.
        """
        artifact_summary = ""
        if state.artifacts:
            artifact_keys = list(state.artifacts.keys())
            artifact_summary = f"Available artifacts: {', '.join(artifact_keys)}"

        context = (
            f"--- PROJECT CONTEXT ---\n"
            f"Original Request: {state.original_request}\n"
            f"Current Plan: {state.plan}\n"
            f"Project Status: {state.status}\n"
            f"{artifact_summary}"
        )
        return context
