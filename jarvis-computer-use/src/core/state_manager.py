import asyncio
from typing import Dict

class ActiveTaskManager:
    """
    Thread-safe, async-safe state manager to hold all currently executing Computer Use tasks.
    Allows for external interrupts, HITL injects, and memory stability without global variables leaking.
    """
    def __init__(self):
        self._tasks: Dict[str, dict] = {}
        self._lock = asyncio.Lock()

    async def register_task(self, task_id: str, state: dict):
        async with self._lock:
            self._tasks[task_id] = state

    async def update_task(self, task_id: str, state: dict):
        async with self._lock:
            self._tasks[task_id] = state

    async def get_task(self, task_id: str) -> dict:
        async with self._lock:
            return self._tasks.get(task_id)

    async def remove_task(self, task_id: str):
        async with self._lock:
            if task_id in self._tasks:
                del self._tasks[task_id]

    async def inject_hitl_approval(self, task_id: str, approved: bool):
        async with self._lock:
            if task_id in self._tasks:
                if approved:
                    self._tasks[task_id]["hitl_approved"] = True
                    self._tasks[task_id]["status"] = "decided"
                else:
                    self._tasks[task_id]["hitl_approved"] = False
                    self._tasks[task_id]["status"] = "failed"

# Singleton instance
state_manager = ActiveTaskManager()
