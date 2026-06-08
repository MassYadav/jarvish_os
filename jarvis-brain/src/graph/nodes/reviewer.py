from typing import Dict, Any
from src.graph.state import AgentState
from src.graph.schema import DAGPlan
from src.graph.security import calculate_dag_risk, requires_human_approval
from src.graph.tools import TOOL_REGISTRY
from src.core.logger import logger

def has_cycle(plan: DAGPlan) -> bool:
    """Kahn's Algorithm (O(V+E)) to detect infinite loops in the plan."""
    in_degree = {node.task_id: 0 for node in plan.nodes}
    adj_list = {node.task_id: [] for node in plan.nodes}
    
    for node in plan.nodes:
        for dep in node.dependencies:
            if dep not in in_degree:
                return True # Hallucinated dependency
            adj_list[dep].append(node.task_id)
            in_degree[node.task_id] += 1
            
    queue = [n for n in in_degree if in_degree[n] == 0]
    visited = 0
    
    while queue:
        current = queue.pop(0)
        visited += 1
        for neighbor in adj_list[current]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)
                
    return visited != len(plan.nodes)

def review_node(state: AgentState) -> Dict[str, Any]:
    logger.info("reviewing_plan", task_id=state["task_id"])
    plan = state.get("dag_plan")
    
    if not plan or not plan.nodes:
        return {"is_valid": False, "errors": ["Empty DAG plan generated."], "retry_count": state["retry_count"] + 1}
        
    if len(plan.nodes) > state.get("max_steps", 10):
        return {"is_valid": False, "errors": [f"DAG exceeds {state['max_steps']} nodes."], "retry_count": state["retry_count"] + 1}

    for node in plan.nodes:
        if node.tool_name not in TOOL_REGISTRY:
            return {"is_valid": False, "errors": [f"SECURITY ALERT: Hallucinated tool '{node.tool_name}'."], "retry_count": state["retry_count"] + 1}
            
    if has_cycle(plan):
        return {"is_valid": False, "errors": ["Topology Error: Cyclic dependencies detected."], "retry_count": state["retry_count"] + 1}

    # Calculate HitL
    risk_score = calculate_dag_risk(plan)
    needs_hitl = requires_human_approval(risk_score)

    return {"is_valid": True, "risk_score": risk_score, "requires_hitl": needs_hitl}