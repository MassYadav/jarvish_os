from typing import TypedDict, Annotated, List, Dict, Any
import operator

class OODAState(TypedDict):
    """
    State tracking for the Computer Use Agent OODA Loop.
    OODA: Observe -> Orient -> Decide -> Act -> Verify
    """
    task_id: str
    objective: str
    
    # Telemetry
    current_screen: str  # Base64 image
    active_window: str
    clipboard: str
    
    # Vision & Decision
    proposed_action: Dict[str, Any]
    
    # History & Recovery
    step_history: Annotated[List[Dict[str, Any]], operator.add]
    errors: Annotated[List[str], operator.add]
    stuck_counter: int
    
    # Execution
    status: str  # e.g., 'running', 'success', 'failed', 'pending_approval'
    hitl_approved: bool
