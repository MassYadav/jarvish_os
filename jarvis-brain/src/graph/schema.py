from pydantic import BaseModel, Field
from typing import List, Dict, Any

class TaskNode(BaseModel):
    task_id: str = Field(description="Unique identifier for this step (e.g., 'read_dir_1')")
    tool_name: str = Field(description="Must exactly match a tool in the Tool Registry")
    payload: Dict[str, Any] = Field(
        description="Arguments for the tool. Use ${task_id.output} to inject data from previous steps."
    )
    dependencies: List[str] = Field(
        default_factory=list, 
        description="List of task_ids that must complete before this node executes."
    )

class DAGPlan(BaseModel):
    nodes: List[TaskNode] = Field(description="Chronologically ordered list of tasks.")