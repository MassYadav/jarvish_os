import uuid
import asyncio
from typing import Dict, Any, Optional
from fastapi import APIRouter, Request, HTTPException, Depends, status
from pydantic import BaseModel

from src.core.security import verify_signature, is_command_safe
from src.tools.base import ToolRequest, ExecutionResult
from src.runtime.executor import execute_command

# Initialize the router
router = APIRouter(prefix="/api/v1", tags=["Execution"])

# In-memory state tracking for active and completed tasks
# In a distributed production system this would use Redis, but for a local OS daemon, memory is optimal.
ACTIVE_TASKS: Dict[str, asyncio.Task] = {}
TASK_RESULTS: Dict[str, ExecutionResult] = {}


# --- Dependency for Cryptographic Security ---
async def verify_hmac(request: Request):
    """
    FastAPI dependency to enforce HMAC SHA-256 zero-trust validation.
    Reads the raw request body before Pydantic parsing occurs.
    """
    signature = request.headers.get("X-Jarvis-Signature")
    if not signature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Jarvis-Signature header."
        )
        
    body_bytes = await request.body()
    if not verify_signature(body_bytes, signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cryptographic signature verification failed."
        )


# --- Background Worker ---
async def background_task_runner(task_id: str, tool_request: ToolRequest):
    """Executes the tool in the background and stores the result upon completion."""
    try:
        # Currently, we only support system shell commands.
        # Future phases will route to browser/desktop tools based on tool_request.tool_name.
        if tool_request.tool_name == "system_shell":
            command = tool_request.parameters.get("command", [])
            
            # Final AST safety check before execution
            if not is_command_safe(command):
                TASK_RESULTS[task_id] = ExecutionResult(
                    success=False,
                    output="",
                    error="Command rejected by AST sanitizer. Unsafe shell syntax detected.",
                    runtime_ms=0.0
                )
                return

            # Execute the isolated command
            result = await execute_command(command, tool_request.timeout_override)
            TASK_RESULTS[task_id] = result
        else:
            TASK_RESULTS[task_id] = ExecutionResult(
                success=False,
                output="",
                error=f"Unsupported tool: {tool_request.tool_name}",
                runtime_ms=0.0
            )
    except asyncio.CancelledError:
        # Handle manual aborts gracefully
        TASK_RESULTS[task_id] = ExecutionResult(
            success=False,
            output="",
            error="Execution was manually aborted by the orchestrator.",
            runtime_ms=0.0
        )
    finally:
        # Clean up the task reference
        if task_id in ACTIVE_TASKS:
            del ACTIVE_TASKS[task_id]


# --- API Models ---
class TaskResponse(BaseModel):
    task_id: str
    status: str

class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[ExecutionResult] = None


# --- Endpoints ---
@router.post("/execute", response_model=TaskResponse, dependencies=[Depends(verify_hmac)])
async def execute_tool(request: ToolRequest):
    """
    Ingests a signed tool payload, spawns a background worker, and returns a tracking ID.
    """
    task_id = str(uuid.uuid4())
    
    # Create and store the background task
    task = asyncio.create_task(background_task_runner(task_id, request))
    ACTIVE_TASKS[task_id] = task
    
    return TaskResponse(task_id=task_id, status="pending")


@router.get("/tasks/{task_id}/status", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """
    Polls the status of an execution. Does not require HMAC since it only reads state, 
    but relies on the unpredictability of the UUID.
    """
    if task_id in TASK_RESULTS:
        return TaskStatusResponse(task_id=task_id, status="completed", result=TASK_RESULTS[task_id])
        
    if task_id in ACTIVE_TASKS:
        return TaskStatusResponse(task_id=task_id, status="running")
        
    raise HTTPException(status_code=404, detail="Task ID not found.")


@router.post("/tasks/{task_id}/abort", response_model=TaskResponse, dependencies=[Depends(verify_hmac)])
async def abort_task(task_id: str):
    """
    Forces the termination of a running task. 
    Requires HMAC signature as this is a destructive operation.
    """
    if task_id in ACTIVE_TASKS:
        # Send the cancellation signal
        ACTIVE_TASKS[task_id].cancel()
        return TaskResponse(task_id=task_id, status="aborting")
        
    if task_id in TASK_RESULTS:
        raise HTTPException(status_code=400, detail="Task has already completed.")
        
    raise HTTPException(status_code=404, detail="Task ID not found.")