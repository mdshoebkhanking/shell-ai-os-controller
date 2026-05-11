from __future__ import annotations

import shutil
import time
from dataclasses import dataclass, field
from typing import Any

from core.events import AIEventType, publish_event


@dataclass(frozen=True)
class RuntimeSnapshot:
    ts: float
    cpu_percent: float = 0.0
    ram_percent: float = 0.0
    disk_percent: float = 0.0
    battery_percent: float | None = None
    power_plugged: bool | None = None
    process_count: int = 0
    network_online: bool = True
    thermal_state: str = "unknown"
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts": self.ts,
            "cpu_percent": self.cpu_percent,
            "ram_percent": self.ram_percent,
            "disk_percent": self.disk_percent,
            "battery_percent": self.battery_percent,
            "power_plugged": self.power_plugged,
            "process_count": self.process_count,
            "network_online": self.network_online,
            "thermal_state": self.thermal_state,
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class ResourcePolicy:
    max_concurrency: int
    allow_heavy_tasks: bool
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_concurrency": self.max_concurrency,
            "allow_heavy_tasks": self.allow_heavy_tasks,
            "reason": self.reason,
        }


class RuntimeMonitor:
    def snapshot(self) -> RuntimeSnapshot:
        try:
            import psutil

            cpu = float(psutil.cpu_percent(interval=None))
            ram = float(psutil.virtual_memory().percent)
            disk = float(psutil.disk_usage("/").percent)
            battery = psutil.sensors_battery()
            process_count = len(psutil.pids())
            return RuntimeSnapshot(
                ts=time.time(),
                cpu_percent=cpu,
                ram_percent=ram,
                disk_percent=disk,
                battery_percent=float(battery.percent) if battery else None,
                power_plugged=bool(battery.power_plugged) if battery else None,
                process_count=process_count,
                network_online=True,
                details={"psutil": True},
            )
        except Exception as exc:
            usage = shutil.disk_usage("/")
            disk_percent = round((usage.used / usage.total) * 100.0, 1) if usage.total else 0.0
            return RuntimeSnapshot(ts=time.time(), disk_percent=disk_percent, details={"psutil": False, "error": str(exc)})

    def policy(self, snapshot: RuntimeSnapshot | None = None) -> ResourcePolicy:
        snap = snapshot or self.snapshot()
        reasons: list[str] = []
        max_concurrency = 4
        allow_heavy = True
        if snap.ram_percent >= 85:
            max_concurrency = 1
            allow_heavy = False
            reasons.append("high RAM usage")
        elif snap.ram_percent >= 70:
            max_concurrency = min(max_concurrency, 2)
            reasons.append("elevated RAM usage")
        if snap.cpu_percent >= 90:
            max_concurrency = 1
            reasons.append("high CPU usage")
        if snap.battery_percent is not None and snap.power_plugged is False and snap.battery_percent <= 25:
            max_concurrency = 1
            allow_heavy = False
            reasons.append("low battery")
        policy = ResourcePolicy(max_concurrency=max_concurrency, allow_heavy_tasks=allow_heavy, reason=", ".join(reasons))
        if reasons:
            publish_event(AIEventType.DEPENDENCY_MISSING, {"runtime_policy": policy.to_dict(), "snapshot": snap.to_dict()}, source="core.runtime")
        return policy

