from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class PolicyRule:
    rule_id: str
    effect: str
    action: str = "*"
    zone: str = "*"
    permission: str = "*"
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"rule_id": self.rule_id, "effect": self.effect, "action": self.action, "zone": self.zone, "permission": self.permission, "reason": self.reason}


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    matched_rules: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"allowed": self.allowed, "matched_rules": list(self.matched_rules), "reasons": list(self.reasons)}


class PolicyEngine:
    def __init__(self, rules: list[PolicyRule] | None = None):
        self.rules = list(rules or [])

    def add_rule(self, rule: PolicyRule) -> None:
        self.rules.append(rule)

    def evaluate(self, contract: dict[str, Any]) -> PolicyDecision:
        matched: list[PolicyRule] = []
        permissions = set(contract.get("permissions") or [])
        for rule in self.rules:
            action_ok = rule.action in {"*", contract.get("action")}
            zone_ok = rule.zone in {"*", contract.get("zone", "standard")}
            permission_ok = rule.permission == "*" or rule.permission in permissions
            if action_ok and zone_ok and permission_ok:
                matched.append(rule)
        denied = [rule for rule in matched if rule.effect.lower() == "deny"]
        allowed_rules = [rule for rule in matched if rule.effect.lower() == "allow"]
        allowed = not denied and (bool(allowed_rules) if matched else True)
        decision = PolicyDecision(allowed, [rule.rule_id for rule in matched], [rule.reason for rule in matched if rule.reason])
        publish_event(AIEventType.POLICY_EVALUATED, {"contract": dict(contract), "decision": decision.to_dict()}, source="core.policy")
        return decision

    @classmethod
    def from_lines(cls, lines: list[str]) -> "PolicyEngine":
        rules: list[PolicyRule] = []
        for idx, line in enumerate(lines, start=1):
            parts = dict(part.split("=", 1) for part in line.split() if "=" in part)
            if not parts:
                continue
            rules.append(PolicyRule(
                rule_id=parts.get("id", f"rule-{idx}"),
                effect=parts.get("effect", "deny"),
                action=parts.get("action", "*"),
                zone=parts.get("zone", "*"),
                permission=parts.get("permission", "*"),
                reason=parts.get("reason", ""),
            ))
        return cls(rules)

