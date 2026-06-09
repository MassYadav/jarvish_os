import asyncio
import time
from typing import List, Optional
from src.core.config import get_settings
from src.tools.base import ExecutionResult


async def execute_command(command: List[str], timeout_override: Optional[int] = None) -> ExecutionResult:
    """
    Executes a pre-tokenized system command asynchronously in an isolated workspace.
    
    Args:
        command: A list of strings representing the executable and its arguments.
        timeout_override: Optional integer to override the global timeout configuration.
        
    Returns:
        ExecutionResult: Standardized telemetry containing success state, outputs, and runtime.
    """
    settings = get_settings()
    
    # Resolve the active timeout (override takes precedence if within valid bounds)
    active_timeout = settings.EXECUTION_TIMEOUT_SECONDS
    if timeout_override is not None and 0 < timeout_override <= 3600:
        active_timeout = timeout_override

    start_time = time.perf_counter()
    
    try:
        # Spawn the subprocess. 
        # MUST NOT USE shell=True to prevent command injection bypasses.
        # Anchor execution strictly to the workspace directory.
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(settings.WORKSPACE_DIR)
        )
        
        # Await completion with strict timeout enforcement
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(), 
                timeout=active_timeout
            )
        except asyncio.TimeoutError:
            # Terminate the zombie process aggressively
            try:
                process.kill()
                await process.wait() # Ensure OS cleans up the PID
            except ProcessLookupError:
                pass # Process already died
                
            runtime_ms = (time.perf_counter() - start_time) * 1000
            return ExecutionResult(
                success=False,
                output="",
                error=f"Execution timed out after {active_timeout} seconds. Process killed.",
                runtime_ms=round(runtime_ms, 2)
            )

        # Decode outputs safely, ignoring malformed byte sequences
        stdout_str = stdout_bytes.decode("utf-8", errors="replace") if stdout_bytes else ""
        stderr_str = stderr_bytes.decode("utf-8", errors="replace") if stderr_bytes else ""
        
        # Check exit code (0 usually indicates success in POSIX/Windows)
        success = (process.returncode == 0)
        
        runtime_ms = (time.perf_counter() - start_time) * 1000
        
        return ExecutionResult(
            success=success,
            output=stdout_str,
            error=stderr_str if not success else None,
            runtime_ms=round(runtime_ms, 2)
        )

    except FileNotFoundError:
        # The underlying OS could not find the executable target (e.g., bad command)
        runtime_ms = (time.perf_counter() - start_time) * 1000
        executable = command[0] if command else "UNKNOWN"
        return ExecutionResult(
            success=False,
            output="",
            error=f"Executable not found: '{executable}'. Ensure it is installed and in the system PATH.",
            runtime_ms=round(runtime_ms, 2)
        )
    except Exception as e:
        # Catch unexpected catastrophic OS-level failures (e.g., out of memory)
        runtime_ms = (time.perf_counter() - start_time) * 1000
        return ExecutionResult(
            success=False,
            output="",
            error=f"Internal Execution Engine Failure: {str(e)}",
            runtime_ms=round(runtime_ms, 2)
        )