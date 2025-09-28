"""Async task manager stub used for offline tests."""
from __future__ import annotations

from typing import Dict

from ..plugin_system import get_logger

logger = get_logger("async_task_manager")


class AsyncTask:
    def __init__(self, task_name: str, wait_before_start: int = 0, run_interval: int = 0) -> None:
        self.task_name = task_name
        self.wait_before_start = wait_before_start
        self.run_interval = run_interval

    async def run(self) -> None:  # pragma: no cover - subclasses override
        logger.debug("Running task %s", self.task_name)


class _AsyncTaskManager:
    def __init__(self) -> None:
        self._tasks: Dict[str, AsyncTask] = {}

    async def add_task(self, task: AsyncTask) -> None:
        logger.info(
            "[async_task_manager] registered task %s (interval=%s)",
            task.task_name,
            task.run_interval,
        )
        self._tasks[task.task_name] = task


async_task_manager = _AsyncTaskManager()

__all__ = ["AsyncTask", "async_task_manager"]
