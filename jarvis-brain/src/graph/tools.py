from src.agents.desktop.file_system import list_directory, read_file
from src.agents.coder.docker_sandbox import execute_python_code
from src.agents.browser.playwright_nav import browse_web # <-- NEW IMPORT

# The Final Universal Tool Registry
TOOL_REGISTRY = {
    "list_directory": list_directory,
    "read_file": read_file,
    "execute_python_code": execute_python_code,
    "browse_web": browse_web, # <-- REGISTERED HERE
    "echo_tool": lambda message: f"Echo: {message}"
}

def get_tool_descriptions() -> str:
    """Provides the tool matrix schemas for the LLM graph planner."""
    return """
    Available Tools:
    1. "list_directory" 
       Payload: {"relative_path": "string (e.g., '', 'folder_name')"}
       Description: Lists files in the workspace.
       
    2. "read_file"
       Payload: {"relative_path": "string (e.g., 'notes.txt')"}
       Description: Reads the contents of a text file in the workspace.
       
    3. "execute_python_code"
       Payload: {"code": "string (The actual raw python code to execute)"}
       Description: Runs Python code safely inside an air-gapped sandboxed Linux container.
       
    4. "browse_web"
       Payload: {"url": "string (e.g., 'https://en.wikipedia.org/wiki/Artificial_intelligence')"}
       Description: Navigates to a website, waits for it to load, and returns the page content as clean, readable Markdown. Use this to research real-time information.
    """