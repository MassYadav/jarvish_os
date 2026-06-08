from typing import Dict, Any
from langchain_core.messages import SystemMessage
from src.graph.state import AgentState
from src.graph.schema import DAGPlan
from src.graph.tools import get_tool_descriptions
from src.core.logger import logger
from src.core.llm_factory import select_and_build_llm

def plan_node(state: AgentState) -> Dict[str, Any]:
    logger.info("generating_dynamic_plan", task_id=state["task_id"], retry_count=state["retry_count"])
    provider_name, llm = select_and_build_llm(state.get("api_keys", {}), state.get("failed_providers", []))
    
    # Force the LLM to output exact JSON matching our Pydantic DAGPlan schema
    structured_llm = llm.with_structured_output(DAGPlan)
    
    context_str = str(state.get("context", {}))
    tools_str = get_tool_descriptions()
    
    error_feedback = ""
    if state.get("errors"):
        # Feed previous failures back so it learns
        error_feedback = f"\nCRITICAL: Previous attempt failed with errors: {'; '.join(state['errors'][-2:])}. FIX THESE ERRORS IN YOUR NEXT PLAN."
    
    prompt = f"""
    You are JARVIS, an autonomous AI OS.
    User Intent: {state['intent']}
    User Context: {context_str}
    
    {tools_str}
    
    Break the intent down into a logical sequence of tools.
    RULES:
    1. Only use tools from the Available Tools list.
    2. Use the 'dependencies' array to force chronological order.
    3. VARIABLE INJECTION: To pass data between steps, use the syntax `${{task_id.output}}` in the payload string.
    {error_feedback}
    """
    
    try:
        dag_plan = structured_llm.invoke([SystemMessage(content=prompt)])
        return {"dag_plan": dag_plan, "active_provider": provider_name}
    except Exception as e:
        logger.warning("planning_error_triggering_failover", provider=provider_name, error=str(e))
        # Because we used `operator.add` in state.py, returning a list appends it!
        return {
            "failed_providers": [provider_name],
            "errors": [f"[{provider_name} Planning Failed]: {str(e)}"],
            "retry_count": state.get("retry_count", 0) + 1
        }