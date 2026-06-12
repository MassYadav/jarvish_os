import base64
from typing import Dict, Any
from src.graph.state import OODAState
from src.core.actuator import ActuatorClient

actuator = ActuatorClient()

async def observe_node(state: OODAState) -> Dict[str, Any]:
    """
    OBSERVE Phase: Gathers telemetry from the physical desktop.
    """
    print(f"[OODA: Observe] Gathering desktop telemetry for task {state['task_id']}")
    
    # Take screenshot (base64)
    screenshot_res = actuator.get_screenshot()
    b64_image = screenshot_res.get("base64", "")
    
    # Get active window
    window_res = actuator.get_active_window()
    active_window = window_res.get("title", "Unknown")
    
    # Get clipboard
    clipboard_res = actuator.get_clipboard()
    clipboard_text = clipboard_res.get("text", "")
    
    return {
        "current_screen": b64_image,
        "active_window": active_window,
        "clipboard": clipboard_text,
        "status": "observing"
    }
