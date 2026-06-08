from src.core.logger import logger
from src.core.config import settings

from langchain_ollama import ChatOllama
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI

def select_and_build_llm(api_keys: dict, failed_providers: list) -> tuple:
    """
    Independent factory to provision the LLM. 
    Decoupled from AgentState to eliminate circular imports with LangGraph nodes.
    """
    user_keys = api_keys or {}
    failed = failed_providers or []
    
    if "groq" not in failed and user_keys.get("groq"):
        logger.info("routing_to_provider", provider="groq")
        return "groq", ChatGroq(temperature=0, groq_api_key=user_keys["groq"], model_name=settings.GROQ_MODEL)
        
    if "gemini" not in failed and user_keys.get("gemini"):
        logger.info("routing_to_provider", provider="gemini")
        return "gemini", ChatGoogleGenerativeAI(temperature=0, google_api_key=user_keys["gemini"], model=settings.GEMINI_MODEL)
        
    logger.info("routing_to_fallback", provider="ollama")
    return "ollama", ChatOllama(base_url=settings.OLLAMA_BASE_URL, model=settings.OLLAMA_MODEL, temperature=0, format="json")