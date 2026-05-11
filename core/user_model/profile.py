from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class UserModel:
    def __init__(self, path: str | Path = ".shell_runtime/user_model.json"):
        self.path = Path(path)

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"preferences": {}, "tool_counts": {}, "workflow_counts": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {"preferences": {}, "tool_counts": {}, "workflow_counts": {}}
        except Exception:
            return {"preferences": {}, "tool_counts": {}, "workflow_counts": {}}

    def _write(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(self.path)

    def set_preference(self, key: str, value: Any) -> None:
        data = self._load()
        data.setdefault("preferences", {})[str(key)] = value
        self._write(data)

    def record_tool_use(self, tool_id: str) -> None:
        data = self._load()
        counts = data.setdefault("tool_counts", {})
        counts[str(tool_id)] = int(counts.get(str(tool_id), 0)) + 1
        self._write(data)

    def export(self) -> dict[str, Any]:
        return self._load()

    def reset(self) -> None:
        self._write({"preferences": {}, "tool_counts": {}, "workflow_counts": {}})

