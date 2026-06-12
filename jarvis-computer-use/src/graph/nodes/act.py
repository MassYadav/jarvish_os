from typing import Dict, Any
from src.graph.state import OODAState
from src.core.actuator import ActuatorClient

actuator = ActuatorClient()

async def act_node(state: OODAState) -> Dict[str, Any]:
    """
    ACT Phase: Executes the verified action against the physical desktop via the Actuator.
    """
    proposed = state.get("proposed_action", {})
    action = proposed.get("action")
    x = proposed.get("x")
    y = proposed.get("y")
    text = proposed.get("text")
    keys = proposed.get("keys")
    
    print(f"[OODA: Act] Executing {action}...")
    
    result = {}
    if action == "CLICK" and x is not None and y is not None:
        result = actuator.click(x, y)
    elif action == "TYPE" and text is not None:
        result = actuator.type_text(text)
    elif action == "HOTKEY" and keys is not None:
        result = actuator.hotkey(keys)
    elif action == "WAIT":
        # System waits implicitly during the loop iteration latency
        result = {"status": "success", "message": "Waited."}
        
    print(f"  -> Actuator Response: {result}")
    
    # We record what we did for the history
    action_taken = f"{action} at {x},{y}" if action == "CLICK" else f"{action} {text or keys or ''}"
    
    return {
        "step_history": [{"action": action_taken, "reasoning": proposed.get("reasoning")}],
        "status": "acting"
    }
