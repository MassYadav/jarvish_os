from typing import Dict, Any
from langchain_core.messages import SystemMessage
from src.graph.state import AgentState
from src.core.logger import logger
from src.core.llm_factory import get_llm_client

def synthesize_node(state: AgentState) -> Dict[str, Any]:
    logger.info("synthesizing_results", task_id=state["task_id"])

    # Build the config dict that get_llm_client expects from current AgentState
    llm_config = {
        **state.get("api_keys", {}),
        **state.get("execution_config", {}),
        "active_provider":  state.get("active_provider") or state.get("api_keys", {}).get("preferred_provider", "groq"),
        "active_model":     state.get("active_model", ""),
        "failed_providers": list(state.get("failed_providers", [])),
    }

    result = get_llm_client(llm_config)

    context_str = str(state.get("step_results", {}))
    errors_str  = "; ".join(state.get("errors", []))

    if state["retry_count"] >= 3:
        status   = "FAILED"
        guidance = "Explain exactly why the system failed after 3 attempts based on the errors."
    else:
        status   = "SUCCESS"
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
        response = result.client.invoke([SystemMessage(content=prompt)])
        return {
            "final_result": response.content,
            # Keep slow_model_active consistent with whichever provider handled synthesis
            "slow_model_active": result.slow_model_active,
        }
    except Exception as e:
        logger.error("synthesizer_failed", error=str(e))
        return {
            "final_result": f"Execution complete, but summary failed: {str(e)}. Raw output: {context_str}",
            "slow_model_active": result.slow_model_active,
        }