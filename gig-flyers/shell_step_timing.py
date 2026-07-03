"""Step timing for shell design jobs."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ShellStepTiming:
    timings_ms: dict[str, int] = field(default_factory=dict)
    cache_hits: dict[str, bool] = field(default_factory=dict)
    openai_calls: int = 0
    _starts: dict[str, float] = field(default_factory=dict, repr=False)

    def start(self, step: str) -> None:
        self._starts[step] = time.perf_counter()

    def stop(self, step: str) -> None:
        started = self._starts.pop(step, None)
        if started is None:
            return
        elapsed = int((time.perf_counter() - started) * 1000)
        self.timings_ms[step] = self.timings_ms.get(step, 0) + elapsed

    def mark_cache(self, key: str, hit: bool) -> None:
        self.cache_hits[key] = hit

    def add_openai_calls(self, count: int = 1) -> None:
        self.openai_calls += count

    def to_dict(self) -> dict[str, Any]:
        return {
            "timings_ms": dict(self.timings_ms),
            "cache_hits": dict(self.cache_hits),
            "openai_calls": self.openai_calls,
        }
