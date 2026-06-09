import os
from pathlib import Path
from typing import List, Dict

# The unbreakable boundary of the Desktop Agent
WORKSPACE_ROOT = Path(os.getenv("JARVIS_WORKSPACE", str(Path.home() / "jarvis_workspace"))).resolve()

def _get_safe_path(requested_path: str) -> Path:
    """Security Gate: Guarantees the path cannot escape the workspace root."""
    # Ensure the workspace root actually exists
    WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
    
    # Resolve resolves all symlinks and '..' components to an absolute path
    target_path = (WORKSPACE_ROOT / requested_path).resolve()
    
    # If the absolute target path doesn't start with the absolute root path, it's a breakout attempt
    if not str(target_path).startswith(str(WORKSPACE_ROOT)):
        raise PermissionError(f"SECURITY BREACH: Attempted to escape workspace jail via {requested_path}")
    
    return target_path

def list_directory(relative_path: str = "") -> str:
    """Lists all files and folders in a given directory inside the workspace."""
    try:
        safe_dir = _get_safe_path(relative_path)
        if not safe_dir.exists() or not safe_dir.is_dir():
            return f"Error: Directory '{relative_path}' does not exist."
            
        items = [f.name + ("/" if f.is_dir() else "") for f in safe_dir.iterdir()]
        if not items:
            return "Directory is empty."
        return "\n".join(items)
    except Exception as e:
        return str(e)

def read_file(relative_path: str) -> str:
    """Reads the contents of a file inside the workspace."""
    try:
        safe_file = _get_safe_path(relative_path)
        if not safe_file.exists() or not safe_file.is_file():
            return f"Error: File '{relative_path}' does not exist."
            
        # Prevent reading massive binary files and crashing the LLM context window
        if safe_file.stat().st_size > 500_000: # 500KB limit
            return "Error: File is too large to read into memory."
            
        return safe_file.read_text(encoding="utf-8")
    except Exception as e:
        return str(e)