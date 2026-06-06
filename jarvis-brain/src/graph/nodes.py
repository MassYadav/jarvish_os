from src.graph.state import AgentState, DAGPlan, TaskNode
from src.memory.postgres import PostgresMemoryAdapter
from src.core.logger import logger
from src.core.config import settings

from langchain_ollama import ChatOllama
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage

memory_adapter = PostgresMemoryAdapter()

def select_and_build_llm(state: AgentState) -> tuple:
    """Prioritizes Groq -> Gemini -> Local Ollama based on provided keys and failure states."""
    user_keys = state.get("api_keys", {})
    failed = state.get("failed_providers", [])
    
    if "groq" not in failed and user_keys.get("groq"):
        logger.info("routing_to_provider", provider="groq")
        return "groq", ChatGroq(temperature=0, groq_api_key=user_keys["groq"], model_name=settings.GROQ_MODEL)
        
    if "gemini" not in failed and user_keys.get("gemini"):
        logger.info("routing_to_provider", provider="gemini")
        return "gemini", ChatGoogleGenerativeAI(temperature=0, google_api_key=user_keys["gemini"], model=settings.GEMINI_MODEL)
        
    logger.info("routing_to_fallback", provider="ollama")
    return "ollama", ChatOllama(base_url=settings.OLLAMA_BASE_URL, model=settings.OLLAMA_MODEL, temperature=0, format="json")

def retrieve_node(state: AgentState) -> AgentState:
    logger.info("retrieving_context", task_id=state["task_id"])
    state["context"] = memory_adapter.get_user_context(state["user_id"])
    return state

def plan_node(state: AgentState) -> AgentState:
    provider_name, llm = select_and_build_llm(state)
    state["active_provider"] = provider_name
    
    prompt = f"""
    You are JARVIS. Intent: {state['intent']}. Context: {str(state.get('context', {}))}
    Generate a JSON execution plan exactly like this schema:
    {{"nodes": [{{"task_id": "1", "tool_name": "echo_tool", "payload": {{"message": "string"}}, "dependencies": []}}]}}
    """
    
    try:
        response = llm.invoke([SystemMessage(content=prompt)])
        
        # Simulating LLM Output Parsing for MVP
        state["dag_plan"] = DAGPlan(nodes=[
            TaskNode(task_id="step_1", tool_name="echo_tool", payload={"message": f"Planned via {provider_name.upper()}: {state['intent']}"})
        ])
    except Exception as e:
        logger.warning("provider_error_triggering_failover", provider=provider_name, error=str(e))
        state["failed_providers"].append(provider_name)
        state["errors"].append(f"[{provider_name}] {str(e)}")
        
        # Hot Failover Recursion
        if provider_name != "ollama":
            return plan_node(state)
            
    return state

def review_node(state: AgentState) -> AgentState:
    plan = state.get("dag_plan")
    if not plan or not plan.nodes:
        state["is_valid"] = False
        state["retry_count"] += 1
        return state
        
    state["is_valid"] = True
    return state

def execute_node(state: AgentState) -> AgentState:
    logger.info("executing_dag", task_id=state["task_id"])
    results = [f"Success: {n.payload.get('message')}" for n in state["dag_plan"].nodes if n.tool_name == "echo_tool"]
    state["final_result"] = " | ".join(results)
    return state