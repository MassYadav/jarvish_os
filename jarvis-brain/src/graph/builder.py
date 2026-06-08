from langgraph.graph import StateGraph, END
from src.graph.state import AgentState

# Correct imports targeting the new directory
from src.graph.nodes.retrieve import retrieve_node 
from src.graph.nodes.planner import plan_node
from src.graph.nodes.reviewer import review_node
from src.graph.nodes.executor import execute_node
from src.graph.nodes.synthesizer import synthesize_node

def review_routing_edge(state: AgentState) -> str:
    """Decides if the graph should execute, pause for HitL, or retry."""
    if not state.get("is_valid"):
        if state.get("retry_count", 0) >= 3:
            return "synthesize" # Break infinite loop
        return "plan"
        
    if state.get("requires_hitl", False):
        return END # Pause graph execution for UI Approval
        
    return "execute"

def execute_routing_edge(state: AgentState) -> str:
    """Routes execution failures back to the planner for self-correction."""
    if not state.get("is_valid"):
        if state.get("retry_count", 0) >= 3:
            return "synthesize"
        return "plan"
    return "synthesize"

def build_graph():
    workflow = StateGraph(AgentState)
    
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("plan", plan_node)
    workflow.add_node("review", review_node)
    workflow.add_node("execute", execute_node)
    workflow.add_node("synthesize", synthesize_node)
    
    workflow.set_entry_point("retrieve")
    workflow.add_edge("retrieve", "plan")
    workflow.add_edge("plan", "review")
    
    workflow.add_conditional_edges(
        "review",
        review_routing_edge,
        {
            "execute": "execute",
            "plan": "plan",
            "synthesize": "synthesize",
            END: END
        }
    )
    
    workflow.add_conditional_edges(
        "execute",
        execute_routing_edge,
        {
            "synthesize": "synthesize",
            "plan": "plan"
        }
    )
    
    workflow.add_edge("synthesize", END)
    
    return workflow.compile()