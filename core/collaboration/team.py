from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from core.events import AIEventType, publish_event


class AgentRole(str, Enum):
    PLANNER = "planner"
    EXECUTOR = "executor"
    VALIDATOR = "validator"
    RESEARCHER = "researcher"
    SUMMARIZER = "summarizer"
    DEBUGGER = "debugger"
    OBSERVER = "observer"
    RECOVERY = "recovery"


class ConsensusRule(str, Enum):
    FIRST_VALID = "FIRST_VALID"
    MAJORITY = "MAJORITY"
    VALIDATOR_DECIDES = "VALIDATOR_DECIDES"


@dataclass(frozen=True)
class RoleAgent:
    agent_id: str
    role: AgentRole
    capabilities: list[str] = field(default_factory=list)
    max_tasks: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "role": self.role.value,
            "capabilities": list(self.capabilities),
            "max_tasks": self.max_tasks,
        }


class CollaborationTeam:
    def __init__(self, max_agents: int = 8, consensus_rule: ConsensusRule = ConsensusRule.VALIDATOR_DECIDES):
        self.max_agents = max(1, int(max_agents))
        self.consensus_rule = consensus_rule
        self._agents: dict[str, RoleAgent] = {}
        self._locks: set[str] = set()

    def spawn(self, role: AgentRole | str, capabilities: list[str] | None = None) -> RoleAgent:
        if len(self._agents) >= self.max_agents:
            raise RuntimeError("agent spawn limit reached")
        role_enum = role if isinstance(role, AgentRole) else AgentRole(str(role))
        agent = RoleAgent(uuid.uuid4().hex, role_enum, list(capabilities or []))
        self._agents[agent.agent_id] = agent
        publish_event(AIEventType.AGENT_SPAWNED, agent.to_dict(), source="core.collaboration")
        return agent

    def acquire_lock(self, owner_id: str, resource: str) -> bool:
        key = str(resource)
        if key in self._locks:
            return False
        self._locks.add(key)
        return True

    def release_lock(self, resource: str) -> None:
        self._locks.discard(str(resource))

    def assignable_agents(self, capability: str) -> list[RoleAgent]:
        return [
            agent for agent in self._agents.values()
            if not capability or capability in agent.capabilities
        ]

    def resolve_conflict(self, proposals: list[dict[str, Any]]) -> dict[str, Any]:
        if not proposals:
            return {"status": "no_consensus", "reason": "no proposals"}
        if self.consensus_rule == ConsensusRule.FIRST_VALID:
            return dict(proposals[0])
        if self.consensus_rule == ConsensusRule.VALIDATOR_DECIDES:
            validators = [p for p in proposals if p.get("role") == AgentRole.VALIDATOR.value]
            if validators:
                return dict(validators[0])
        votes: dict[str, int] = {}
        for proposal in proposals:
            key = str(proposal.get("decision") or proposal.get("result") or "")
            votes[key] = votes.get(key, 0) + 1
        best = max(votes.items(), key=lambda item: item[1])[0]
        return {"status": "consensus", "decision": best, "votes": votes}

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_agents": self.max_agents,
            "consensus_rule": self.consensus_rule.value,
            "agents": [agent.to_dict() for agent in self._agents.values()],
            "locks": sorted(self._locks),
        }

