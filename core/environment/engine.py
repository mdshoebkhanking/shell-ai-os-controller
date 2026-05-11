from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from core.events import AIEventType, publish_event


class NetworkQuality(str, Enum):
    OFFLINE = "OFFLINE"
    UNSTABLE = "UNSTABLE"
    OK = "OK"
    FAST = "FAST"


@dataclass(frozen=True)
class EnvironmentSnapshot:
    ts: float = field(default_factory=time.time)
    network_quality: NetworkQuality = NetworkQuality.OK
    battery_percent: float | None = None
    power_plugged: bool | None = None
    thermal_state: str = "unknown"
    gpu_available: bool = False
    peripherals: list[str] = field(default_factory=list)
    provider_status: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts": self.ts,
            "network_quality": self.network_quality.value,
            "battery_percent": self.battery_percent,
            "power_plugged": self.power_plugged,
            "thermal_state": self.thermal_state,
            "gpu_available": self.gpu_available,
            "peripherals": list(self.peripherals),
            "provider_status": dict(self.provider_status),
        }


@dataclass(frozen=True)
class EnvironmentPolicy:
    offline_mode: bool
    reduce_heavy_tasks: bool
    pause_cloud_workflows: bool
    max_concurrency: int
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "offline_mode": self.offline_mode,
            "reduce_heavy_tasks": self.reduce_heavy_tasks,
            "pause_cloud_workflows": self.pause_cloud_workflows,
            "max_concurrency": self.max_concurrency,
            "reasons": list(self.reasons),
        }


class EnvironmentalIntelligence:
    def assess(self, snapshot: EnvironmentSnapshot) -> EnvironmentPolicy:
        reasons: list[str] = []
        offline = snapshot.network_quality == NetworkQuality.OFFLINE
        pause_cloud = snapshot.network_quality in {NetworkQuality.OFFLINE, NetworkQuality.UNSTABLE}
        reduce_heavy = False
        max_concurrency = 4
        if offline:
            reasons.append("network offline")
        elif pause_cloud:
            reasons.append("network unstable")
        if snapshot.battery_percent is not None and snapshot.power_plugged is False and snapshot.battery_percent <= 25:
            reduce_heavy = True
            max_concurrency = 1
            reasons.append("low battery")
        if snapshot.thermal_state.lower() in {"serious", "critical", "hot"}:
            reduce_heavy = True
            max_concurrency = 1
            reasons.append("thermal pressure")
        if any(state.lower() in {"down", "degraded"} for state in snapshot.provider_status.values()):
            reasons.append("provider degraded")
        policy = EnvironmentPolicy(offline, reduce_heavy, pause_cloud, max_concurrency, reasons)
        publish_event(AIEventType.ENVIRONMENT_SNAPSHOT, {"snapshot": snapshot.to_dict(), "policy": policy.to_dict()}, source="core.environment")
        return policy

