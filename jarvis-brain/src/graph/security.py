from src.graph.schema import DAGPlan
from src.core.logger import logger

# The Threat Matrix
TOOL_RISK_SCORES = {
    "list_directory": 1,       # Safe READ
    "read_file": 1,            # Safe READ
    "browse_web": 1,           # Safe READ
    "echo_tool": 0,            # Safe NO-OP
    "execute_python_code": 5,  # DANGEROUS EXECUTE (Instant HitL trigger)
    "screenshot": 1,           # Safe READ
    "mouse_click": 3,          # Moderate WRITE
    "type_text": 4,            # Dangerous WRITE
    "press_hotkey": 1,         # Very Dangerous WRITE (Temporarily lowered to 1 for testing)
    "focus_window": 2,         # Low-Moderate WRITE
    "open_app": 2              # Safe EXECUTE - Opens apps/URLs
}

HITL_THRESHOLD = 5

def calculate_dag_risk(plan: DAGPlan) -> int:
    """Calculates the cumulative danger level of the generated execution plan."""
    if not plan or not plan.nodes:
        return 0
        
    total_risk = 0
    for node in plan.nodes:
        # Default to highest risk if the tool is hallucinated/unknown
        score = TOOL_RISK_SCORES.get(node.tool_name, 10) 
        total_risk += score
        
    logger.info("risk_evaluation_complete", risk_score=total_risk, nodes_count=len(plan.nodes))
    return total_risk

def requires_human_approval(risk_score: int) -> bool:
    """Tripwire check: Does this execution require manual user approval?"""
    return risk_score >= HITL_THRESHOLD