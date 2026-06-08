import operator
from typing import TypedDict, List, Dict, Any, Optional, Annotated
from src.graph.schema import DAGPlan

class AgentState(TypedDict):
    # Base State
    task_id: str
    user_id: str
    intent: str
    context: Dict[str, Any]
    
    # Cognitive State
    dag_plan: Optional[DAGPlan]
    step_results: Dict[str, str]
    
    # Annotated with operator.add so errors from Planner and Reviewer combine instead of overwriting
    errors: Annotated[List[str], operator.add] 
    retry_count: int
    is_valid: bool
    
    # Execution Budget (NEW FIX)
    max_steps: int
    tool_calls_used: int
    max_execution_time: int
    
    # Security State
    risk_score: int
    requires_hitl: bool
    
    # Final Output
    final_result: str
    
    # BYOAK Engine State
    api_keys: Dict[str, str]
    # Annotated so failovers stack gracefully
    failed_providers: Annotated[List[str], operator.add] 
    active_provider: str