from typing import Dict, Any
from src.graph.state import OODAState
from src.core.vision import VisionClient
from src.core.actuator import ActuatorClient

actuator = ActuatorClient()
vision_client = VisionClient()

async def verify_node(state: OODAState) -> Dict[str, Any]:
    """
    VERIFY Phase: Assesses if the physical action had the intended UI outcome.
    """
    print(f"[OODA: Verify] Verifying outcome of action...")
    
    # Take post-action screenshot
    screenshot_res = actuator.get_screenshot()
    post_action_b64 = screenshot_res.get("base64", "")
    
    pre_action_b64 = state["current_screen"]
    last_action = state["step_history"][-1] if state.get("step_history") else {"action": "None"}
    
    success = await vision_client.verify_action(
        pre_action_b64=pre_action_b64,
        post_action_b64=post_action_b64,
        action_taken=last_action["action"],
        objective=state["objective"]
    )
    
    current_stuck = state.get("stuck_counter", 0)
    if success:
        print("  -> VLM Verification: SUCCESS")
        return {"stuck_counter": 0, "status": "verified"}
    else:
        print("  -> VLM Verification: FAILURE / NO CHANGE DETECTED")
        return {"stuck_counter": current_stuck + 1, "status": "verified_failed"}

async def recovery_node(state: OODAState) -> Dict[str, Any]:
    """
    RECOVERY Phase: Triggers when stuck_counter > 3. 
    Hits ESC and forces a re-evaluation of the screen.
    """
    print(f"[OODA: Recovery] System appears stuck. Triggering escape sequence...")
    actuator.hotkey(["esc"])
    
    return {
        "stuck_counter": 0,
        "step_history": [{"action": "RECOVERY: Hit ESC to break loop", "reasoning": "stuck_counter exceeded limit."}],
        "errors": ["Stuck loop detected. Attempted recovery."],
        "status": "recovering"
    }
