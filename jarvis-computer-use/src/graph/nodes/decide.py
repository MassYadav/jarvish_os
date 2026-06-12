from typing import Dict, Any
from src.graph.state import OODAState

# Keywords that trigger Human-In-The-Loop approval
DESTRUCTIVE_KEYWORDS = ["delete", "submit", "purchase", "buy", "apply", "deploy", "git push", "rm -rf"]

async def decide_node(state: OODAState) -> Dict[str, Any]:
    """
    DECIDE Phase: Validates the action, enforces HITL security.
    """
    proposed = state.get("proposed_action", {})
    action = proposed.get("action", "")
    reasoning = proposed.get("reasoning", "").lower()
    text = str(proposed.get("text", "")).lower()
    
    print(f"[OODA: Decide] Evaluating action: {action}")
    
    # Check if action is 'DONE'
    if action == "DONE":
        return {"status": "success"}
    
    if action == "CLARIFICATION_NEEDED":
        print(f"  -> Universal Clarification Triggered. Reason: {reasoning}")
        return {"status": "CLARIFICATION_NEEDED"}
    
    # Check for HITL overrides
    if not state.get("hitl_approved", False):
        requires_hitl = False
        for kw in DESTRUCTIVE_KEYWORDS:
            if kw in reasoning or kw in text:
                requires_hitl = True
                break
                
        if requires_hitl:
            print(f"  -> SECURITY BLOCK: '{action}' requires HITL approval.")
            return {"status": "pending_approval"}
            
    print("  -> Action Approved. Proceeding to Act.")
    return {"status": "decided"}
