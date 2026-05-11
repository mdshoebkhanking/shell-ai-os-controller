from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TrustSubject:
    subject_id: str
    subject_type: str
    score: float
    reasons: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {"subject_id": self.subject_id, "subject_type": self.subject_type, "score": self.score, "reasons": list(self.reasons)}


class TrustEngine:
    def score_tool(self, tool_id: str) -> TrustSubject:
        from core.tools.reputation import ToolReputationStore

        rep = ToolReputationStore().get(tool_id)
        if not rep.total:
            return TrustSubject(tool_id, "tool", 0.5, ["no history"])
        score = max(0.0, min(1.0, rep.success_rate - min(0.4, rep.failures / max(1, rep.total))))
        reasons = [f"success_rate={rep.success_rate}", f"failures={rep.failures}", f"avg_latency_ms={rep.average_latency_ms}"]
        return TrustSubject(tool_id, "tool", round(score, 3), reasons)

    def score_plugin(self, manifest: dict[str, Any], *, verified: bool = False) -> TrustSubject:
        permissions = set(manifest.get("permissions") or [])
        score = 0.8 if verified else 0.45
        reasons = ["verified manifest" if verified else "unverified plugin"]
        risky = permissions & {"shell.execute", "desktop.control", "filesystem.write", "api.keys"}
        if risky:
            score -= 0.2
            reasons.append(f"elevated permissions: {', '.join(sorted(risky))}")
        return TrustSubject(str(manifest.get("name") or "plugin"), "plugin", round(max(0.0, score), 3), reasons)

