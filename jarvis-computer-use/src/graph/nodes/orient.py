from typing import Dict, Any
from src.graph.state import OODAState
from src.core.vision import VisionClient

vision_client = VisionClient()

async def orient_node(state: OODAState) -> Dict[str, Any]:
    """
    ORIENT Phase: VLM processes the visual telemetry to determine what needs to be done.
    """
    print(f"[OODA: Orient] Analyzing screen with VLM for task {state['task_id']}")
    
    action = await vision_client.analyze_screen(
        base64_img=state["current_screen"],
        objective=state["objective"],
        active_window=state["active_window"],
        history=state.get("step_history", [])
    )
    
    proposed = {
        "action": action.action,
        "x": action.x,
        "y": action.y,
        "text": action.text,
        "keys": action.keys,
        "reasoning": action.reasoning
    }
    
    print(f"  -> Decided: {proposed['action']} | Reasoning: {proposed['reasoning']}")
    
    return {
        "proposed_action": proposed,
        "status": "orienting"
    }
