from typing import Dict, Any
from langchain_core.messages import SystemMessage
from src.graph.state import AgentState
from src.core.logger import logger
from src.core.llm_factory import select_and_build_llm

def synthesize_node(state: AgentState) -> Dict[str, Any]:
    logger.info("synthesizing_results", task_id=state["task_id"])
    provider_name, llm = select_and_build_llm(state.get("api_keys", {}), state.get("failed_providers", []))
    
    context_str = str(state.get("step_results", {}))
    errors_str = "; ".join(state.get("errors", []))
    
    if state["retry_count"] >= 3:
        status = "FAILED"
        guidance = "Explain exactly why the system failed after 3 attempts based on the errors."
    else:
        status = "SUCCESS"
        guidance = "Summarize the actions taken and the results. Be concise, professional, and act like JARVIS."

    prompt = f"""
    You are JARVIS. Respond directly to the user.
    User Intent: {state['intent']}
    Execution Status: {status}
    
    Tool Data Gathered: {context_str}
    Errors encountered: {errors_str}
    
    {guidance}
    """
    
    try:
        response = llm.invoke([SystemMessage(content=prompt)])
        return {"final_result": response.content}
    except Exception as e:
        logger.error("synthesizer_failed", error=str(e))
        return {"final_result": f"Execution complete, but summary failed: {str(e)}. Raw output: {context_str}"}