import re
import time
from typing import Dict, Any, List
from src.graph.state import AgentState
from src.graph.tools import TOOL_REGISTRY
from src.core.logger import logger

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
        if not progress: break
    return sorted_nodes

def interpolate_payload(payload: Dict[str, Any], step_results: Dict[str, str]) -> Dict[str, Any]:
    """Injects ${step_id.output} variables dynamically."""
    interpolated = {}
    pattern = re.compile(r'\$\{([^}]+)\.output\}')
    
    for key, value in payload.items():
        if isinstance(value, str):
            def replacer(match):
                task_ref = match.group(1)
                if task_ref not in step_results:
                    raise KeyError(f"Variable injection failed: '{task_ref}' output missing.")
                return step_results[task_ref]
            interpolated[key] = pattern.sub(replacer, value)
        else:
            interpolated[key] = value
    return interpolated

def execute_node(state: AgentState) -> Dict[str, Any]:
    logger.info("executing_dynamic_dag", task_id=state["task_id"])
    
    plan = state["dag_plan"]
    # Copy dictionary to avoid mutability bugs
    step_results = dict(state.get("step_results", {})) 
    sorted_nodes = _topological_sort(plan.nodes)
    
    start_time = time.time()
    tool_calls_used = state.get("tool_calls_used", 0)
    
    for node in sorted_nodes:
        if node.task_id in step_results:
            continue
            
        if time.time() - start_time > state.get("max_execution_time", 300):
            return {"is_valid": False, "errors": ["Execution Timeout."], "step_results": step_results, "retry_count": state["retry_count"] + 1}
            
        try:
            final_payload = interpolate_payload(node.payload, step_results)
            tool_func = TOOL_REGISTRY[node.tool_name]
            result = tool_func(**final_payload)
            
            # Context window truncation (Iron Man safety bounds)
            if len(result) > 10000:
                result = result[:10000] + "\n...[TRUNCATED FOR LLM LIMITS]"
                
            step_results[node.task_id] = result
            tool_calls_used += 1
            logger.info("step_executed", step=node.task_id)
            
        except Exception as e:
            logger.error("step_execution_failed", step=node.task_id, error=str(e))
            return {"is_valid": False, "errors": [f"[Step {node.task_id} Failed]: {str(e)}"], "step_results": step_results, "retry_count": state["retry_count"] + 1}
            
    return {"step_results": step_results, "tool_calls_used": tool_calls_used}