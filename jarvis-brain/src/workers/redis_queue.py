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

    # Unpack the execution config forwarded from the Gateway
    execution_config: dict = payload_dict.get("execution_config", {})
    active_model: str = execution_config.get("active_model", "")

    # Inject Phase 4 initialization state with explicit budgets
    task_intent = payload_dict.get("intent")
    is_resume = task_intent is None

    dag_plan_obj = None
    step_results = {}
    is_valid = False
    hitl_approved = False

    if is_resume:
        # Load from DB for an approved HITL resume
        with engine.connect() as conn:
            res = conn.execute(
                text("SELECT execution_plan, step_results FROM agent_tasks WHERE task_id = :tid"),
                {"tid": task_id}
            ).fetchone()
        if res:
            try:
                if res[0] and res[0] != "{}" and res[0] != {}:
                    from src.graph.schema import DAGPlan
                    if isinstance(res[0], dict):
                        dag_plan_obj = DAGPlan.model_validate(res[0])
                    else:
                        dag_plan_obj = DAGPlan.model_validate_json(res[0])
                    is_valid = True
                    hitl_approved = True
                if res[1] and res[1] != "{}" and res[1] != {}:
                    step_results = res[1] if isinstance(res[1], dict) else json.loads(res[1])
            except Exception as e:
                logger.error("failed_to_resume_state", error=str(e))

    initial_state = {
        "task_id": task_id,
        "user_id": payload_dict.get("user_id", "system"),
        "intent": task_intent or "RESUMING APPROVED TASK",
        "context": {}, "dag_plan": dag_plan_obj, "step_results": step_results, 
        "errors": [], "retry_count": 0, "is_valid": is_valid,
        
        # Clarification engine variables
        "waiting_for_user": False, "user_clarification_response": payload_dict.get("user_clarification_response", None),
        "clarification_question": None,
        
        # Execution Budget Initialization
        "max_steps": 10, "tool_calls_used": 0, "max_execution_time": 300,
        
        # Security defaults
        "risk_score": 0, "requires_hitl": False, "hitl_approved": hitl_approved,
        "final_result": "",
        "api_keys": payload_dict.get("api_keys", {}),
        "failed_providers": [], "active_provider": "",

        # Execution config from UI
        "active_model": active_model,
        "execution_config": execution_config,

        # Slow-model flag — set True by factory when Ollama fallback is engaged
        "slow_model_active": False,

        # Dual-Core Orchestrator defaults
        "browser_context": "",
        "vision_escalation_active": False,
        "vision_telemetry": [],
    }

    try:
        final_state = graph.invoke(initial_state)
        
        # HITL Interception Logic
        if final_state.get("waiting_for_user"):
            status = "WAITING_FOR_USER"
            result_payload = final_state.get("clarification_question", "Execution paused: Waiting for user clarification.")
        elif final_state.get("requires_hitl"):
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
        slow_model_active = final_state.get("slow_model_active", False)

    except Exception as e:
        logger.error("graph_execution_failed", error=str(e))
        status, result_payload = "FAILED", str(e)
        execution_plan_json, step_results_json = "{}", "{}"
        risk_score, requires_hitl, slow_model_active = 0, False, False

    # Expanded SQL Update pushing all cognitive metadata
    with engine.connect() as conn:
        conn.execute(text("""
            UPDATE agent_tasks 
            SET status = :s, 
                result_payload = :p,
                execution_plan = :ep,
                step_results = :sr,
                risk_score = :rs,
                requires_hitl = :rh,
                slow_model_active = :sma
            WHERE task_id = :tid
        """), {
            "s": status, "p": result_payload, "tid": task_id,
            "ep": execution_plan_json, "sr": step_results_json,
            "rs": risk_score, "rh": requires_hitl,
            "sma": slow_model_active,
        })
        conn.commit()
        
    logger.info("worker_finished_task", task_id=task_id, status=status, slow_model=slow_model_active)

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

if __name__ == "__main__":
    listen_to_queue()