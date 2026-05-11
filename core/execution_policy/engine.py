from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ExecutionBudget:
    max_cost_score: float = 1.0
    max_tokens: int = 4000
    prefer_local: bool = True
    offline: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"max_cost_score": self.max_cost_score, "max_tokens": self.max_tokens, "prefer_local": self.prefer_local, "offline": self.offline}


@dataclass(frozen=True)
class ProviderCandidate:
    provider_id: str
    local: bool
    cost_score: float
    speed_score: float
    quality_score: float
    max_tokens: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "local": self.local,
            "cost_score": self.cost_score,
            "speed_score": self.speed_score,
            "quality_score": self.quality_score,
            "max_tokens": self.max_tokens,
        }


class ExecutionPolicyEngine:
    def estimate_tokens(self, text: str) -> int:
        return max(1, int(len(str(text or "")) / 4))

    def choose_provider(self, candidates: list[ProviderCandidate], *, budget: ExecutionBudget, prompt: str = "") -> ProviderCandidate | None:
        tokens = self.estimate_tokens(prompt)
        viable = [
            c for c in candidates
            if c.cost_score <= budget.max_cost_score
            and c.max_tokens >= min(tokens, budget.max_tokens)
            and (not budget.offline or c.local)
        ]
        if not viable:
            return None
        viable.sort(key=lambda c: (
            0 if (budget.prefer_local and c.local) else 1,
            c.cost_score,
            -c.quality_score,
            -c.speed_score,
        ))
        return viable[0]

    def compression_needed(self, text: str, *, budget: ExecutionBudget) -> bool:
        return self.estimate_tokens(text) > budget.max_tokens

