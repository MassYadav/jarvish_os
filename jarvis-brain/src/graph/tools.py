from src.agents.desktop.file_system import list_directory, read_file
from src.agents.coder.docker_sandbox import execute_python_code
from src.agents.browser.playwright_nav import browse_web
from src.agents.actuator.client import ActuatorClient

# Instantiate the Actuator Client
actuator = ActuatorClient()

def screenshot() -> dict:
    """Captures a screenshot of the user's physical desktop. Takes no arguments."""
    return actuator.screenshot_desktop()

def mouse_click(x: int, y: int) -> dict:
    """Clicks the physical mouse at the specified x and y screen coordinates."""
    return actuator.click_at(x, y)

def type_text(text: str) -> dict:
    """Types the provided text on the physical keyboard at the current cursor position."""
    return actuator.type_text(text)

def press_hotkey(keys: list[str]) -> dict:
    """Presses a combination of keys on the physical keyboard. Use this for hotkeys like ['win'] or ['ctrl', 'c']."""
    return actuator.press_hotkey(keys)

def focus_window(title: str) -> dict:
    """Focuses the physical window with the specified title."""
    return actuator.focus_window(title)

def open_app_or_url(target: str) -> dict:
    """Opens a local application or a website URL on the physical machine."""
    return actuator.open_application(target)

# The Final Universal Tool Registry
TOOL_REGISTRY = {
    "list_directory": list_directory,
    "read_file": read_file,
    "execute_python_code": execute_python_code,
    "browse_web": browse_web,
    "echo_tool": lambda message: f"Echo: {message}",
    "screenshot": screenshot,
    "open_app": open_app_or_url,
    "mouse_click": mouse_click,
    "type_text": type_text,
    "press_hotkey": press_hotkey,
    "focus_window": focus_window
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
       Payload: {"url": "string (e.g., 'https://en.wikipedia.org')"}
       Description: Navigates to a website and returns the page content.
       
    5. "screenshot"
       Payload: {}
       Description: Captures a screenshot of the desktop.
       
    6. "mouse_click"
       Payload: {"x": "int", "y": "int"}
       Description: Clicks at specified x, y coordinates on the desktop.
       
    7. "type_text"
       Payload: {"text": "string"}
       Description: Types text at the current cursor position.
       
    8. "press_hotkey"
       Payload: {"keys": ["string list of key names"]}
       Description: Presses a combination of hotkeys on the physical keyboard (e.g., ["win"], ["ctrl", "c"]).
       
    9. "focus_window"
       Payload: {"title": "string (window title)"}
       Description: Focuses on a window with the specified title.

    10. "open_app"
       Payload: {"target": "string (e.g., 'chrome', 'notepad', 'https://youtube.com')"}
       Description: Opens a native desktop application or a website URL in the default browser.
    """