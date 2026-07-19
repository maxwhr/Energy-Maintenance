from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(slots=True)
class BoundedExecutionResult:
    values: list[Any]
    errors: dict[int, str]
    max_workers: int


class BoundedRetrievalExecutor:
    """Bounded synchronous executor with deterministic input-order output."""

    def __init__(self, *, max_concurrency: int = 3):
        self.max_concurrency = max(1, int(max_concurrency))

    def execute(self, jobs: list[Any], callback: Callable[[Any], Any]) -> BoundedExecutionResult:
        values: list[Any] = [None] * len(jobs)
        errors: dict[int, str] = {}
        if not jobs:
            return BoundedExecutionResult(values, errors, self.max_concurrency)
        workers = min(self.max_concurrency, len(jobs))
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="rag-bounded") as executor:
            futures: dict[Future, int] = {
                executor.submit(callback, job): index for index, job in enumerate(jobs)
            }
            for future in as_completed(futures):
                index = futures[future]
                try:
                    values[index] = future.result()
                except Exception as exc:  # noqa: BLE001 - callers retain successful channel results.
                    errors[index] = type(exc).__name__
        return BoundedExecutionResult(values, errors, workers)
