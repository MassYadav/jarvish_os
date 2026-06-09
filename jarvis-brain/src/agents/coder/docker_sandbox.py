import os
import docker
from pathlib import Path
from src.core.logger import logger

# Align with Phase 3A workspace
WORKSPACE_ROOT = Path(os.getenv("JARVIS_WORKSPACE", str(Path.home() / "jarvis_workspace"))).resolve()

def execute_python_code(code: str) -> str:
    """
    Executes raw Python code inside a secure, ephemeral Docker container.
    Guarantees isolation, resource caps, and auto-cleanup.
    """
    # Ensure the workspace directory physically exists
    WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
    
    try:
        # Connect to the local Docker daemon
        client = docker.from_env()
    except Exception as e:
        logger.error("docker_daemon_connection_failed", error=str(e))
        return "Error: Cannot connect to Docker Daemon. Ensure Docker Desktop is running."

    container = None
    try:
        logger.info("spinning_up_sandbox", image="python:3.11-alpine")
        
        # Provision the ephemeral isolation capsule
        container = client.containers.run(
            image="python:3.11-alpine",
            # Run python command directly passing the code string safely wrapped
            command=["python", "-c", code],
            # Bind mount our local safe workspace inside the container's /workspace folder
            volumes={
                str(WORKSPACE_ROOT): {
                    "bind": "/workspace",
                    "mode": "rw"
                }
            },
            working_dir="/workspace",
            detach=True,
            mem_limit="512m",       # Hard memory ceiling to stop malicious/runaway code
            network_disabled=True,  # Complete air-gap: code cannot dial out to the internet
        )
        
        # Enforce execution timeout limit (10 seconds max)
        try:
            result = container.wait(timeout=10)
            exit_code = result.get("StatusCode", 0)
        except Exception:
            container.kill()
            return "Error: Execution timed out (Maximum limit: 10 seconds)."
            
        # Extract terminal outputs
        stdout = container.logs(stdout=True, stderr=False).decode("utf-8")
        stderr = container.logs(stdout=False, stderr=True).decode("utf-8")
        
        if exit_code != 0:
            return f"[Execution Failed with Exit Code {exit_code}]:\n{stderr if stderr else stdout}"
            
        return stdout if stdout.strip() else "Code executed successfully with no visible console output."
        
    except Exception as e:
        logger.error("sandbox_runtime_exception", error=str(e))
        return f"Container Runtime Error: {str(e)}"
        
    finally:
        # Immutable cleanup guarantee: Always destroy the evidence/container
        if container:
            try:
                container.remove(force=True)
                logger.info("sandbox_destroyed_successfully")
            except Exception:
                pass