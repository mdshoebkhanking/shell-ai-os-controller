from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable


@dataclass
class BatchQueue:
    max_batch_size: int = 8
    items: list[Any] = field(default_factory=list)

    def add(self, item: Any) -> list[Any]:
        self.items.append(item)
        if len(self.items) >= self.max_batch_size:
            return self.flush()
        return []

    def flush(self) -> list[Any]:
        out = list(self.items)
        self.items.clear()
        return out


class AsyncExecutionPool:
    def __init__(self, concurrency: int = 4):
        self.concurrency = max(1, int(concurrency))
        self._semaphore: asyncio.Semaphore | None = None

    def _get_semaphore(self) -> asyncio.Semaphore:
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.concurrency)
        return self._semaphore

    async def run(self, fn: Callable[..., Awaitable[Any]], *args: Any, **kwargs: Any) -> Any:
        async with self._get_semaphore():
            return await fn(*args, **kwargs)

    async def map(self, fn: Callable[[Any], Awaitable[Any]], items: list[Any]) -> list[Any]:
        return await asyncio.gather(*(self.run(fn, item) for item in items))
