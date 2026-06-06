import json
from redis import Redis
from sqlalchemy import create_engine, text
from src.graph.builder import build_graph
from src.core.logger import logger
from src.core.config import settings

engine = create_engine(settings.DATABASE_URL)
redis_conn = Redis.from_url(settings.REDIS_URL)
graph = build_graph()

def process_task(payload_dict: dict):
    task_id = payload_dict["task_id"]
    logger.info("worker_started_task", task_id=task_id)
    
    with engine.connect() as conn:
        conn.execute(text("UPDATE agent_tasks SET status = 'RUNNING' WHERE task_id = :tid"), {"tid": task_id})
        conn.commit()

    initial_state = {
        "task_id": task_id,
        "user_id": payload_dict["user_id"],
        "intent": payload_dict["intent"],
        "context": {}, "dag_plan": None, "errors": [], "retry_count": 0, "is_valid": False, "final_result": "",
        "api_keys": payload_dict.get("api_keys", {}),
        "failed_providers": [], "active_provider": ""
    }

    try:
        final_state = graph.invoke(initial_state)
        status = "COMPLETED" if final_state.get("final_result") else "FAILED"
        result_payload = final_state.get("final_result", str(final_state.get("errors")))
    except Exception as e:
        logger.error("graph_execution_failed", error=str(e))
        status, result_payload = "FAILED", str(e)

    with engine.connect() as conn:
        conn.execute(text("UPDATE agent_tasks SET status = :s, result_payload = :p WHERE task_id = :tid"), 
                     {"s": status, "p": result_payload, "tid": task_id})
        conn.commit()
    logger.info("worker_finished_task", task_id=task_id, status=status)

import redis

# ... (keep the process_task function exactly as it is) ...

def listen_to_queue():
    logger.info("worker_listening", queue="jarvis_execution_queue")
    while True:
        try:
            # Change timeout=0 to timeout=5. 
            # This allows the TCP socket to breathe and prevents idle drop-offs.
            task_data = redis_conn.blpop("jarvis_execution_queue", timeout=5)
            
            if task_data:
                _, payload_bytes = task_data
                process_task(json.loads(payload_bytes))
                
        except redis.exceptions.TimeoutError:
            # Expected behavior if the socket drops. Ignore and keep listening.
            continue
        except Exception as e:
            logger.error("worker_runtime_error", error=str(e))
            # Prevent rapid crash-looping if Redis goes down
            import time
            time.sleep(2)