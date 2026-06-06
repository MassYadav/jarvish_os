from typing import TypedDict, List, Dict, Any, Optional
from pydantic import BaseModel, Field

class TaskNode(BaseModel):
    task_id: str
    tool_name: str
    payload: Dict[str, Any]
    dependencies: List[str] = Field(default_factory=list)

class DAGPlan(BaseModel):
    nodes: List[TaskNode]

class AgentState(TypedDict):
    task_id: str
    user_id: str
    intent: str
    context: Dict[str, Any]
    dag_plan: Optional[DAGPlan]
    errors: List[str]
    retry_count: int
    is_valid: bool
    final_result: str
    
    # BYOAK Failover State
    api_keys: Dict[str, str]
    failed_providers: List[str]
    active_provider: str