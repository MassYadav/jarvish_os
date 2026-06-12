import os
import json
import asyncio
import uuid
import structlog
from redis import asyncio as aioredis
from redis.exceptions import TimeoutError as RedisTimeoutError, ConnectionError as RedisConnectionError
from dotenv import load_dotenv

load_dotenv()
logger = structlog.get_logger()

from src.graph.builder import build_ooda_graph
from src.graph.state import OODAState
from src.core.state_manager import state_manager

REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6380/0")
QUEUE_NAME = "jarvis_computer_use_queue"
TELEMETRY_CHANNEL = "jarvis_telemetry"

class ComputerUseDaemon:
    def __init__(self):
        self.redis = aioredis.from_url(
            REDIS_URL, 
            decode_responses=True,
            health_check_interval=10,
            socket_timeout=5,
            retry_on_timeout=True
        )
        self.graph = build_ooda_graph()

    async def _publish_telemetry(self, task_id: str, state: dict):
        # We selectively extract fields to avoid sending enormous payloads, 
        # but include current_screen (base64) so UI can stream desktop.
        payload = {
            "task_id": task_id,
            "status": state.get("status"),
            "proposed_action": state.get("proposed_action", {}),
            "stuck_counter": state.get("stuck_counter", 0),
            "hitl_requested": state.get("status") == "pending_approval",
            "current_screen": state.get("current_screen"),
            "reason": state.get("proposed_action", {}).get("reasoning", state.get("reason", ""))
        }
        await self.redis.publish(TELEMETRY_CHANNEL, json.dumps(payload))

    async def _execute_task(self, task_data: dict):
        task_id = task_data.get("task_id", str(uuid.uuid4()))
        objective = task_data.get("objective", "")
        
        logger.info("starting_computer_use_task", task_id=task_id, objective=objective)
        
        # Override env API keys if passed from Gateway
        api_keys = task_data.get("api_keys", {})
        if "gemini_key" in api_keys:
            os.environ["GEMINI_API_KEY"] = api_keys["gemini_key"]

        current_state = OODAState(
            task_id=task_id,
            objective=objective,
            current_screen="",
            active_window="",
            clipboard="",
            proposed_action={},
            step_history=[],
            errors=[],
            stuck_counter=0,
            status="starting",
            hitl_approved=False
        )

        await state_manager.register_task(task_id, current_state)

        try:
            while current_state["status"] not in ["success", "failed", "CLARIFICATION_NEEDED"]:
                # ainvoke runs the graph logic asynchronously based on current state
                try:
                    result = await self.graph.ainvoke(current_state)
                    current_state.update(result)
                except Exception as ainvoke_e:
                    if "429" in str(ainvoke_e) or "RESOURCE_EXHAUSTED" in str(ainvoke_e):
                        logger.warning("API Rate Limit Hit. Sleeping for 65 seconds...")
                        await asyncio.sleep(65)
                        continue
                    else:
                        raise ainvoke_e
                
                await state_manager.update_task(task_id, current_state)
                await self._publish_telemetry(task_id, current_state)

                # Check if VLM explicitly requested WAIT (e.g. from a caught exception inside VisionClient)
                proposed = current_state.get("proposed_action", {})
                if proposed.get("action") == "WAIT":
                    logger.warning("API Rate Limit Hit. Sleeping for 65 seconds...")
                    await asyncio.sleep(65)

                if current_state["status"] == "pending_approval":
                    logger.info("hitl_approval_required", task_id=task_id)
                    # Block and poll local state until hitl is injected from UI
                    while current_state["status"] == "pending_approval":
                        await asyncio.sleep(1)
                        current_state = await state_manager.get_task(task_id)

                await asyncio.sleep(1) # API limit pacing
                
        except Exception as e:
            logger.error("task_execution_failed", task_id=task_id, error=str(e))
            current_state["status"] = "failed"
            current_state["errors"].append(str(e))
            await self._publish_telemetry(task_id, current_state)
        finally:
            await state_manager.remove_task(task_id)

    async def start(self):
        logger.info("computer_use_daemon_started", queue=QUEUE_NAME)
        while True:
            try:
                # Use timeout=2 to prevent Docker from silently dropping idle infinite blocks
                result = await self.redis.blpop(QUEUE_NAME, timeout=2)
                if result:
                    _, payload = result
                    task_data = json.loads(payload)
                    # Spawn isolated Task to prevent one bad task from taking down the Daemon
                    asyncio.create_task(self._execute_task(task_data))
            except (TimeoutError, RedisTimeoutError, RedisConnectionError):
                # Silently catch and retry idle network drops caused by Windows Docker
                continue
            except Exception as e:
                logger.error("queue_polling_error", error=str(e))
                await asyncio.sleep(5)

async def main():
    daemon = ComputerUseDaemon()
    await daemon.start()

if __name__ == "__main__":
    asyncio.run(main())
