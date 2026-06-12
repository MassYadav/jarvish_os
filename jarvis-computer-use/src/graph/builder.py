from langgraph.graph import StateGraph, END
from src.graph.state import OODAState
from src.graph.nodes.observe import observe_node
from src.graph.nodes.orient import orient_node
from src.graph.nodes.decide import decide_node
from src.graph.nodes.act import act_node
from src.graph.nodes.verify import verify_node, recovery_node

def should_recover(state: OODAState):
    if state.get("stuck_counter", 0) > 3:
        return "recover"
    return "observe"

def route_decision(state: OODAState):
    status = state.get("status")
    if status == "success":
        return END
    elif status == "pending_approval":
        # Pauses execution. When resumed (state updated), it should re-decide or act.
        return END  # For now, end the graph, orchestrator will resume it.
    return "act"

def build_ooda_graph():
    workflow = StateGraph(OODAState)
    
    workflow.add_node("observe", observe_node)
    workflow.add_node("orient", orient_node)
    workflow.add_node("decide", decide_node)
    workflow.add_node("act", act_node)
    workflow.add_node("verify", verify_node)
    workflow.add_node("recovery", recovery_node)
    
    # Entry Point
    workflow.set_entry_point("observe")
    
    # Observe -> Orient
    workflow.add_edge("observe", "orient")
    
    # Orient -> Decide
    workflow.add_edge("orient", "decide")
    
    # Decide -> Act or END (success / pending_approval)
    workflow.add_conditional_edges("decide", route_decision, {
        "act": "act",
        END: END
    })
    
    # Act -> Verify
    workflow.add_edge("act", "verify")
    
    # Verify -> Observe (loop back) or Recovery
    workflow.add_conditional_edges("verify", should_recover, {
        "observe": "observe",
        "recover": "recovery"
    })
    
    # Recovery -> Observe
    workflow.add_edge("recovery", "observe")
    
    return workflow.compile()
