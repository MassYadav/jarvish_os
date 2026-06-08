import json
import redis
from redis import Redis
from sqlalchemy import create_engine, text
from src.graph.builder import build_graph
from src.core.logger import logger
from src.core.config import settings

engine = create_engine(settings.DATABASE_URL)
redis_conn = Redis.from_url(settings.REDIS_URL)

# Delay builder initialization slightly if circular imports were an issue, 
# but it should be clean now.
graph = build_graph()

def process_task(payload_dict: dict):
    task_id = payload_dict["task_id"]
    logger.info("worker_started_task", task_id=task_id)
    
    with engine.connect() as conn:
        conn.execute(text("UPDATE agent_tasks SET status = 'RUNNING' WHERE task_id = :tid"), {"tid": task_id})
        conn.commit()

    # Inject Phase 4 initialization state with explicit budgets
    initial_state = {
        "task_id": task_id,
        "user_id": payload_dict["user_id"],
        "intent": payload_dict["intent"],
        "context": {}, "dag_plan": None, "step_results": {}, 
        "errors": [], "retry_count": 0, "is_valid": False,
        
        # Execution Budget Initialization
        "max_steps": 10, "tool_calls_used": 0, "max_execution_time": 300,
        
        # Security defaults
        "risk_score": 0, "requires_hitl": False, "final_result": "",
        "api_keys": payload_dict.get("api_keys", {}),
        "failed_providers": [], "active_provider": ""
    }

    try:
        final_state = graph.invoke(initial_state)
        
        # HITL Interception Logic
        if final_state.get("requires_hitl"):
            status = "PENDING_APPROVAL"
            result_payload = "Execution paused for Human-in-the-Loop authorization."
        else:
            status = "COMPLETED" if final_state.get("final_result") else "FAILED"
            result_payload = final_state.get("final_result", str(final_state.get("errors")))
            
        # Serialize Phase 4 outputs for Postgres JSONB columns
        dag_plan_obj = final_state.get("dag_plan")
        execution_plan_json = dag_plan_obj.model_dump_json() if dag_plan_obj else "{}"
        step_results_json = json.dumps(final_state.get("step_results", {}))
        risk_score = final_state.get("risk_score", 0)
        requires_hitl = final_state.get("requires_hitl", False)

    except Exception as e:
        logger.error("graph_execution_failed", error=str(e))
        status, result_payload = "FAILED", str(e)
        execution_plan_json, step_results_json = "{}", "{}"
        risk_score, requires_hitl = 0, False

    # Expanded SQL Update pushing all cognitive metadata (FIXED SYNTAX)
    with engine.connect() as conn:
        conn.execute(text("""
            UPDATE agent_tasks 
            SET status = :s, 
                result_payload = :p,
                execution_plan = :ep,
                step_results = :sr,
                risk_score = :rs,
                requires_hitl = :rh
            WHERE task_id = :tid
        """), {
            "s": status, "p": result_payload, "tid": task_id,
            "ep": execution_plan_json, "sr": step_results_json,
            "rs": risk_score, "rh": requires_hitl
        })
        conn.commit()
        
    logger.info("worker_finished_task", task_id=task_id, status=status)

def listen_to_queue():
    logger.info("worker_listening", queue="jarvis_execution_queue")
    while True:
        try:
            task_data = redis_conn.blpop("jarvis_execution_queue", timeout=5)
            if task_data:
                _, payload_bytes = task_data
                process_task(json.loads(payload_bytes))
        except redis.exceptions.TimeoutError:
            continue
        except Exception as e:
            logger.error("worker_runtime_error", error=str(e))
            import time
            time.sleep(2)