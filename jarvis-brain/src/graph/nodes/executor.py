import re
import time
import json
from typing import Dict, Any, List
from src.graph.state import AgentState
from src.graph.tools import TOOL_REGISTRY
from src.graph.escalation import (
    triage_exception,
    TriageVerdict,
    VisionEscalationPayload,
    escalate_to_vision_daemon,
)
from src.graph.context_handover import handover_manager
from src.core.logger import logger

# Browser tool names that qualify for context handover during escalation
_BROWSER_TOOLS = frozenset({
    "browser_navigate", "browser_click", "browser_type", "browser_scrape_text",
    "browse_web",
})


def _topological_sort(nodes: List[Any]) -> List[Any]:
    sorted_nodes = []
    visited = set()
    while len(sorted_nodes) < len(nodes):
        progress = False
        for node in nodes:
            if node.task_id not in visited and all(dep in visited for dep in node.dependencies):
                sorted_nodes.append(node)
                visited.add(node.task_id)
                progress = True
        if not progress: 
            break
    return sorted_nodes

def interpolate_payload(payload: Dict[str, Any], step_results: Dict[str, str]) -> Dict[str, Any]:
    """Injects ${step_id.output} variables dynamically into flat or nested structures."""
    pattern = re.compile(r'\$\{([^}]+)\.output\}')
    
    def _interpolate(val: Any) -> Any:
        if isinstance(val, str):
            def replacer(match):
                task_ref = match.group(1)
                if task_ref not in step_results:
                    raise KeyError(f"Variable injection failed: '{task_ref}' output missing.")
                return str(step_results[task_ref])
            return pattern.sub(replacer, val)
        elif isinstance(val, dict):
            return {k: _interpolate(v) for k, v in val.items()}
        elif isinstance(val, list):
            return [_interpolate(item) for item in val]
        return val

    return _interpolate(payload)


def _attempt_vision_escalation(
    node: Any,
    exc: Exception,
    state: AgentState,
    step_results: Dict[str, str],
) -> Dict[str, Any]:
    """
    Dual-Core Escalation: Fast-Path failed, hand over to VLM daemon.

    1. Extract browser session context (URL, cookies, localStorage, DOM)
    2. Push escalation payload to jarvis_computer_use_queue
    3. Block-listen on jarvis_telemetry until daemon completes or times out
    4. Return merged state with vision telemetry
    """
    logger.info(
        "dual_core_escalation_triggered",
        step=node.task_id,
        tool=node.tool_name,
        exception_type=type(exc).__name__,
    )

    # 1. Extract browser session handover (safe — never raises)
    handover = {}
    if node.tool_name in _BROWSER_TOOLS:
        try:
            handover_payload = handover_manager.extract_handover()
            handover = handover_payload.model_dump()
        except Exception as handover_err:
            logger.warning("handover_extraction_failed", error=str(handover_err)[:200])

    # 2. Build typed escalation payload
    escalation = VisionEscalationPayload(
        task_id=state["task_id"],
        objective=state["intent"],
        failed_step=node.task_id,
        failed_tool=node.tool_name,
        failure_reason=str(exc)[:500],
        handover_context=handover,
        api_keys=state.get("api_keys", {}),
    )

    # 3. Push to Redis queue + listen for telemetry
    vision_result = escalate_to_vision_daemon(escalation)

    vision_status = vision_result.get("vision_status", "timeout")
    telemetry_frames = vision_result.get("telemetry_frames", [])

    # 4. Record escalation result as the step's output
    step_results[node.task_id] = json.dumps({
        "escalated_to_vision": True,
        "vision_status": vision_status,
        "frame_count": len(telemetry_frames),
    })

    if vision_status == "success":
        logger.info("vision_escalation_succeeded", step=node.task_id)
        return {
            "step_results": step_results,
            "vision_escalation_active": False,
            "vision_telemetry": telemetry_frames,
        }
    else:
        logger.warning("vision_escalation_did_not_succeed", step=node.task_id, status=vision_status)
        return {
            "is_valid": False,
            "errors": [f"[Step {node.task_id}] Vision escalation ended with status: {vision_status}"],
            "step_results": step_results,
            "retry_count": state.get("retry_count", 0) + 1,
            "vision_escalation_active": False,
            "vision_telemetry": telemetry_frames,
        }


def execute_node(state: AgentState) -> Dict[str, Any]:
    """
    Dual-Core Hybrid Executor.

    For each DAG step:
      1. Attempt Core 1 (Deterministic Fast-Path): direct tool invocation
      2. On exception → O(1) triage lookup in EXCEPTION_TRIAGE registry
      3. Verdict RETRY → re-attempt once
      4. Verdict ESCALATE → extract context, push to VLM daemon, stream telemetry
      5. Verdict ABORT → fail the DAG and return to planner
    """
    logger.info("executing_dual_core_dag", task_id=state.get("task_id"))
    
    plan = state["dag_plan"]
    step_results = dict(state.get("step_results", {})) 
    browser_context = state.get("browser_context", "")
    sorted_nodes = _topological_sort(plan.nodes)
    
    start_time = time.time()
    tool_calls_used = state.get("tool_calls_used", 0)
    
    for node in sorted_nodes:
        if node.task_id in step_results:
            continue
            
        if time.time() - start_time > state.get("max_execution_time", 300):
            return {
                "is_valid": False, 
                "errors": ["Execution Timeout."], 
                "step_results": step_results, 
                "retry_count": state.get("retry_count", 0) + 1
            }

        retries_remaining = 1  # Allow one Fast-Path retry before escalation
            
        while True:
            try:
                # --- CORE 1: DETERMINISTIC FAST-PATH ---
                final_payload = interpolate_payload(node.payload, step_results)
                tool_func = TOOL_REGISTRY[node.tool_name]
                raw_result = tool_func(**final_payload)
                
                # Intercept Universal Clarification Engine tool call
                if isinstance(raw_result, dict) and raw_result.get("status") == "WAITING_FOR_USER":
                    question = raw_result.get("question", "")
                    logger.info("universal_clarification_triggered_text", step=node.task_id, question=question)
                    
                    # Push question to voice out queue
                    from src.workers.redis_queue import redis_conn
                    redis_conn.rpush("jarvis_voice_out_queue", json.dumps({
                        "task_id": state["task_id"],
                        "question": question
                    }))
                    
                    return {
                        "waiting_for_user": True,
                        "clarification_question": question,
                        "step_results": step_results,
                        "tool_calls_used": tool_calls_used,
                        "browser_context": browser_context
                    }

                # Normalize outputs safely into clean strings
                if isinstance(raw_result, (dict, list)):
                    string_result = json.dumps(raw_result, ensure_ascii=False)
                else:
                    string_result = str(raw_result)
                
                # Context window truncation guardrail
                if len(string_result) > 10000:
                    string_result = string_result[:10000] + "\n...[TRUNCATED FOR LLM LIMITS]"
                    
                step_results[node.task_id] = string_result
                tool_calls_used += 1
                logger.info("step_executed_fast_path", step=node.task_id)

                # Persist scraped web context into the high-level AgentState
                if node.tool_name == "browser_scrape_text":
                    if isinstance(raw_result, dict) and "text" in raw_result:
                        browser_context = raw_result["text"]
                    else:
                        browser_context = string_result

                break  # Success — exit retry loop, advance to next node

            except Exception as exc:
                # --- O(1) EXCEPTION TRIAGE ---
                verdict = triage_exception(exc)

                if verdict == TriageVerdict.RETRY_FAST_PATH and retries_remaining > 0:
                    retries_remaining -= 1
                    logger.info(
                        "fast_path_retrying",
                        step=node.task_id,
                        exception=type(exc).__name__,
                    )
                    time.sleep(0.5)  # Brief cooldown before retry
                    continue

                elif verdict == TriageVerdict.ESCALATE_TO_VISION:
                    # --- CORE 2: COGNITIVE VISION-PATH ---
                    vision_result = _attempt_vision_escalation(node, exc, state, step_results)
                    
                    # Intercept Clarification from Vision Daemon
                    vision_status = json.loads(step_results.get(node.task_id, "{}")).get("vision_status", "")
                    if vision_status == "CLARIFICATION_NEEDED":
                        logger.info("universal_clarification_triggered_vision", step=node.task_id)
                        # The telemetry frame reason holds the context
                        reason = "I need your help with the screen. I couldn't complete the objective."
                        if vision_result.get("vision_telemetry"):
                            last_frame = vision_result["vision_telemetry"][-1]
                            if last_frame.get("reason"):
                                reason = last_frame["reason"]
                                
                        from src.workers.redis_queue import redis_conn
                        redis_conn.rpush("jarvis_voice_out_queue", json.dumps({
                            "task_id": state["task_id"],
                            "question": reason
                        }))
                        
                        return {
                            "waiting_for_user": True,
                            "clarification_question": reason,
                            "step_results": step_results,
                            "tool_calls_used": tool_calls_used,
                            "browser_context": browser_context,
                            "vision_escalation_active": False,
                            "vision_telemetry": vision_result.get("vision_telemetry", [])
                        }
                    
                    return vision_result

                else:
                    # --- ABORT: Return to planner for self-correction ---
                    logger.error(
                        "step_execution_aborted",
                        step=node.task_id,
                        exception=type(exc).__name__,
                        error=str(exc)[:300],
                    )
                    return {
                        "is_valid": False, 
                        "errors": [f"[Step {node.task_id} Failed]: {str(exc)}"], 
                        "step_results": step_results, 
                        "retry_count": state.get("retry_count", 0) + 1
                    }
            
    return {
        "step_results": step_results, 
        "tool_calls_used": tool_calls_used, 
        "browser_context": browser_context
    }