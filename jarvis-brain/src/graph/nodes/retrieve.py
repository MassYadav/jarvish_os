from typing import Dict, Any
from src.graph.state import AgentState
from src.memory.postgres import PostgresMemoryAdapter
from src.core.logger import logger

memory_adapter = PostgresMemoryAdapter()

def retrieve_node(state: AgentState) -> Dict[str, Any]:
    logger.info("retrieving_context", task_id=state["task_id"])
    context = memory_adapter.get_user_context(state["user_id"])
    
    # LangGraph will automatically merge this dict into the main AgentState
    return {"context": context}