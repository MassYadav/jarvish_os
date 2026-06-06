from langgraph.graph import StateGraph, END
from src.graph.state import AgentState
from src.graph.nodes import retrieve_node, plan_node, review_node, execute_node

def should_continue(state: AgentState) -> str:
    if state["is_valid"]: return "execute"
    if state["retry_count"] >= 3: return END
    return "plan"

def build_graph():
    workflow = StateGraph(AgentState)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("plan", plan_node)
    workflow.add_node("review", review_node)
    workflow.add_node("execute", execute_node)
    
    workflow.set_entry_point("retrieve")
    workflow.add_edge("retrieve", "plan")
    workflow.add_edge("plan", "review")
    workflow.add_conditional_edges("review", should_continue, {"execute": "execute", END: END, "plan": "plan"})
    workflow.add_edge("execute", END)
    
    return workflow.compile()