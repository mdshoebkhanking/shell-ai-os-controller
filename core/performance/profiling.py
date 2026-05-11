from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator


@dataclass
class StartupProfiler:
    marks: list[dict[str, Any]] = field(default_factory=list)

    def mark(self, name: str, **metadata: Any) -> None:
        self.marks.append({"name": name, "ts": time.perf_counter(), "metadata": dict(metadata)})

    @contextmanager
    def span(self, name: str, **metadata: Any) -> Iterator[None]:
        start = time.perf_counter()
        try:
            yield
        finally:
            self.marks.append({
                "name": name,
                "duration_ms": round((time.perf_counter() - start) * 1000.0, 3),
                "metadata": dict(metadata),
            })

    def report(self) -> dict[str, Any]:
        return {"marks": list(self.marks), "count": len(self.marks)}

