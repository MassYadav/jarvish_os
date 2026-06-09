from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict


class ToolRequest(BaseModel):
    """
    The standard input contract for any execution request hitting the actuator.
    Acts as the deserialization target for the FastAPI payload.
    """
    
    tool_name: str = Field(
        ..., 
        min_length=1,
        description="The registered internal name of the tool to execute (e.g., 'system_shell', 'browser_click')."
    )
    
    parameters: Dict[str, Any] = Field(
        default_factory=dict, 
        description="The keyword arguments required by the specific tool."
    )
    
    timeout_override: Optional[int] = Field(
        default=None, 
        gt=0, 
        le=3600,
        description="Optional override for the global execution timeout, in seconds."
    )
    
    model_config = ConfigDict(
        frozen=True,  # Make the request immutable once instantiated
        extra="forbid" # Reject arbitrary undocumented payload fields to prevent injection
    )


class ExecutionResult(BaseModel):
    """
    The standard output contract for any execution result leaving the actuator.
    Provides structured telemetry for the LangGraph orchestrator.
    """
    
    success: bool = Field(
        ..., 
        description="True if the tool executed successfully (exit code 0), False otherwise."
    )
    
    output: str = Field(
        default="", 
        description="Standard output (stdout) or JSON stringified result of the tool."
    )
    
    error: Optional[str] = Field(
        default=None, 
        description="Standard error (stderr) or Python exception traceback if execution failed."
    )
    
    runtime_ms: float = Field(
        ..., 
        ge=0.0,
        description="Precise execution duration in milliseconds for performance observability."
    )
    
    model_config = ConfigDict(
        frozen=True,
        extra="ignore"
    )