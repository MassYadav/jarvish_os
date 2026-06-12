from typing import Dict, Any
from langchain_core.messages import SystemMessage
from src.graph.state import AgentState
from src.graph.schema import DAGPlan
from src.graph.tools import get_tool_descriptions
from src.core.logger import logger
from src.core.llm_factory import get_llm_client
from src.agents.browser.playwright_nav import (
    browser_navigate,
    browser_click,
    browser_type,
    browser_scrape_text
)

def plan_node(state: AgentState) -> Dict[str, Any]:
    if state.get("hitl_approved") and state.get("dag_plan"):
        logger.info("plan_already_approved_skipping_generation", task_id=state["task_id"])
        return {}
        
    logger.info("generating_dynamic_plan", task_id=state["task_id"], retry_count=state["retry_count"])

    # Build the config dict that get_llm_client expects from current AgentState
    llm_config = {
        **state.get("api_keys", {}),
        **state.get("execution_config", {}),
        "active_provider":  state.get("active_provider") or state.get("api_keys", {}).get("preferred_provider", "groq"),
        "active_model":     state.get("active_model", ""),
        "failed_providers": list(state.get("failed_providers", [])),
    }

    result = get_llm_client(llm_config)

    # Bind the structural browser tools directly to the LLM client
    client_with_tools = result.client.bind_tools([
        browser_navigate,
        browser_click,
        browser_type,
        browser_scrape_text
    ])

    # Force the LLM to output exact JSON matching our Pydantic DAGPlan schema
    structured_llm = client_with_tools.with_structured_output(DAGPlan)

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
    Browser Context: {state.get('browser_context', '')}

    {tools_str}

    Break the intent down into a logical sequence of tools.
    RULES:
    1. Only use tools from the Available Tools list.
    2. Use the 'dependencies' array to force chronological order.
    3. VARIABLE INJECTION: To pass data between steps, use the syntax `${{task_id.output}}` in the payload string.

    STRICT ENGINEERING DIRECTIVES:
    - When processing user commands involving websites, web profiles, streaming platforms, or online authentication (e.g., YouTube, LinkedIn, Email), you MUST use the structural `browser_*` tools. Do not simulate generic OS mouse movements or coordinate guessing.
    - For multi-stage automated sequences (e.g., navigating to LinkedIn, extracting text, logging in), use a strict State Machine pattern: (1) Navigate to the page, (2) Scrape the current text to verify if you are already logged in or if a captcha/form exists, (3) Use explicit text or ID selectors to input data or click buttons, (4) Re-verify the new page state before proceeding.
    - UNIVERSAL CLARIFICATION ENGINE: You are a collaborative AI assistant. If you lack the required context, or if the graphical interface prevents you from completing a step (e.g., missing contacts, incorrect passwords, blocked pages), you must IMMEDIATELY halt execution and formulate a concise, conversational question to ask the user for guidance using the `ask_user_for_clarification` tool.

    {error_feedback}
    """

    try:
        dag_plan = structured_llm.invoke([SystemMessage(content=prompt)])
        return {
            "dag_plan": dag_plan,
            "active_provider": result.provider,
            # Propagate slow_model_active so the Gateway can surface the warning toast
            "slow_model_active": result.slow_model_active,
        }
    except Exception as e:
        logger.warning("planning_error_triggering_failover", provider=result.provider, error=str(e))
        # Because we used `operator.add` in state.py, returning a list appends it!
        return {
            "failed_providers": [result.provider],
            "errors": [f"[{result.provider} Planning Failed]: {str(e)}"],
            "retry_count": state.get("retry_count", 0) + 1,
        }