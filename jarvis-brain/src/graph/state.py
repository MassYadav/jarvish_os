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
    
    # Universal Clarification Engine State
    waiting_for_user: bool
    user_clarification_response: Optional[str]
    clarification_question: Optional[str]
    
    # Execution Budget (NEW FIX)
    max_steps: int
    tool_calls_used: int
    max_execution_time: int
    
    # Security State
    risk_score: int
    requires_hitl: bool
    hitl_approved: bool
    
    # Final Output
    final_result: str
    browser_context: str
    
    # BYOAK Engine State
    api_keys: Dict[str, str]
    # Annotated so failovers stack gracefully
    failed_providers: Annotated[List[str], operator.add] 
    active_provider: str
    active_model: str  # Specific model name selected by user (e.g. "llama-3.1-70b-versatile")
    # Raw execution config block forwarded from the Gateway
    execution_config: Dict[str, str]
    # Set to True when Ollama local fallback is engaged — surfaced as a frontend performance warning
    slow_model_active: bool

    # Dual-Core Orchestrator State
    vision_escalation_active: bool   # True when the VLM Computer Use Daemon is handling the task
    vision_telemetry: List[Dict]     # Accumulates live telemetry frames from the VLM daemon