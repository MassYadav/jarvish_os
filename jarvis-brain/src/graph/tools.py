import os
import json
import logging
from pathlib import Path

try:
    from PyPDF2 import PdfReader
except ImportError:
    PdfReader = None

from langchain_core.messages import HumanMessage
from src.core.llm_factory import get_llm_client
from src.agents.desktop.file_system import list_directory, read_file
from src.agents.coder.docker_sandbox import execute_python_code
from src.agents.browser.playwright_nav import (
    browse_web,
    browser_navigate,
    browser_click,
    browser_type,
    browser_scrape_text
)
from src.agents.actuator.client import ActuatorClient
from src.graph.escalation import shutdown_escalation

logger = logging.getLogger(__name__)

# Instantiate the High-Performance Actuator Client
actuator = ActuatorClient()

def shutdown_agent_tools():
    """Explicitly releases persistent connection pools during daemon shutdown."""
    try:
        actuator.close()
        logger.info("actuator_client_connection_pool_closed")
    except Exception as e:
        logger.error(f"failed_to_close_actuator_pool: {e}")

    try:
        shutdown_escalation()
        logger.info("escalation_redis_pool_closed")
    except Exception as e:
        logger.error(f"failed_to_close_escalation_pool: {e}")

def screenshot() -> dict:
    """Captures a screenshot of the user's physical desktop. Takes no arguments."""
    return actuator.screenshot_desktop()

def mouse_click(x: int, y: int) -> dict:
    """Clicks the physical mouse at the specified x and y screen coordinates."""
    return actuator.click_at(x, y)

def type_text(text: str) -> dict:
    """Types the provided text on the physical keyboard at the current cursor position."""
    return actuator.type_text(text)

def press_hotkey(keys: list[str]) -> dict:
    """Presses a combination of keys on the physical keyboard. Use this for hotkeys like ['win'] or ['ctrl', 'c']."""
    return actuator.press_hotkey(keys)

def focus_window(title: str) -> dict:
    """Focuses the physical window with the specified title."""
    return actuator.focus_window(title)

def open_app_or_url(target: str) -> dict:
    """Opens a local application or a website URL on the physical machine."""
    return actuator.open_application(target)

def ask_user_for_clarification(question: str, context: str) -> dict:
    """
    Universal Clarification Engine tool. Puts the state into WAITING_FOR_USER and pushes the question to Voice OS.
    """
    return {"status": "WAITING_FOR_USER", "question": question, "context": context}

def vision_escalation(objective: str) -> dict:
    """
    Meta-tool: Escalates a task to the VLM Computer Use Daemon.
    This is triggered automatically by the Dual-Core executor when
    the Fast-Path fails — not invoked directly by the LLM planner.
    """
    return {"status": "escalation_placeholder", "objective": objective}

def scan_and_analyze_local_resumes(folder_path: str = r"C:\Users\mass0\OneDrive\Desktop\jarvish_os\resumes", job_description_text: str = "") -> str:
    """
    Scans local resumes and evaluates the best match for a job description using the internal LLM context.
    """
    if not job_description_text:
        return "Error: No job_description_text provided."
        
    target_dir = Path(folder_path)
    if not target_dir.exists() or not target_dir.is_dir():
        return f"Error: The designated resume folder does not exist at {folder_path}"
        
    resumes_text = {}
    
    try:
        for file_path in target_dir.iterdir():
            if file_path.is_file():
                if file_path.suffix.lower() == '.pdf' and PdfReader:
                    try:
                        reader = PdfReader(str(file_path))
                        text = "".join(page.extract_text() for page in reader.pages if page.extract_text())
                        resumes_text[str(file_path)] = text[:4000] # Limit tokens for rapid matrix
                    except Exception as e:
                        logger.warning(f"Failed to parse PDF {file_path}: {e}")
                elif file_path.suffix.lower() in ['.txt', '.md']:
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            resumes_text[str(file_path)] = f.read()[:4000]
                    except Exception as e:
                        logger.warning(f"Failed to read text file {file_path}: {e}")
                        
        if not resumes_text:
            return "Error: No readable resumes (PDF/TXT) found in the designated folder."
            
        prompt = f"""You are JARVIS's Memory Mesh processor. 
Evaluate the following resumes against the Job Description.

Job Description:
{job_description_text}

Resumes:
"""
        for fp, text in resumes_text.items():
            prompt += f"--- Resume Path: {fp} ---\n{text}\n\n"
            
        prompt += """Determine the single best resume filename/path that structurally maps best against the job description.
Return the absolute path of the winning resume file on the FIRST LINE.
Return a 2-sentence architectural justification on the following lines.
Do not add any markdown formatting, just the path and the justification."""
        
        # O(1) Matrix inference execution
        llm_result = get_llm_client({}) 
        response = llm_result.client.invoke([HumanMessage(content=prompt)])
        
        return str(response.content)
        
    except Exception as e:
        logger.error(f"Failed during scan_and_analyze_local_resumes: {e}")
        return f"Error during resume analysis: {e}"

def get_user_profile_context(field_category: str) -> dict:
    """
    Reads the user_profile.json natively in O(1) time and returns the targeted branch.
    """
    profile_path = Path(__file__).parent.parent.parent / "user_profile.json"
    
    if not profile_path.exists():
        return {"error": f"user_profile.json not found at {profile_path}"}
        
    try:
        with open(profile_path, 'r', encoding='utf-8') as f:
            profile_data = json.load(f)
            
        if field_category in profile_data:
            return {field_category: profile_data[field_category]}
        elif field_category == "all" or not field_category:
            return profile_data
        else:
            return {"error": f"Field category '{field_category}' not found in user profile."}
            
    except Exception as e:
        logger.error(f"Failed to parse user_profile.json: {e}")
        return {"error": f"Failed to parse user profile: {e}"}



# The Final Universal Tool Registry
TOOL_REGISTRY = {
    "list_directory": list_directory,
    "read_file": read_file,
    "execute_python_code": execute_python_code,
    "browse_web": browse_web,
    "browser_navigate": browser_navigate,
    "browser_click": browser_click,
    "browser_type": browser_type,
    "browser_scrape_text": browser_scrape_text,
    "echo_tool": lambda message: f"Echo: {message}",
    "screenshot": screenshot,
    "open_app": open_app_or_url,
    "mouse_click": mouse_click,
    "type_text": type_text,
    "press_hotkey": press_hotkey,
    "focus_window": focus_window,
    "vision_escalation": vision_escalation,
    "ask_user_for_clarification": ask_user_for_clarification,
    "scan_and_analyze_local_resumes": scan_and_analyze_local_resumes,
    "get_user_profile_context": get_user_profile_context,
}

def get_tool_descriptions() -> str:
    """Provides the tool matrix schemas for the LLM graph planner."""
    return """
    Available Tools:
    1. "list_directory" 
       Payload: {"relative_path": "string (e.g., '', 'folder_name')"}
       Description: Lists files in the workspace directory.
       
    2. "read_file"
       Payload: {"relative_path": "string (e.g., 'notes.txt')"}
       Description: Reads the contents of a text file in the workspace.
       
    3. "execute_python_code"
       Payload: {"code": "string (The actual raw python code to execute)"}
       Description: Runs Python code safely inside an air-gapped sandboxed Linux container.
       
    4. "browse_web"
       Payload: {"url": "string (e.g., 'https://en.wikipedia.org')"}
       Description: Navigates to a website and returns the page content.
       
    5. "screenshot"
       Payload: {}
       Description: Captures a real-time screenshot of the desktop.
       
    6. "mouse_click"
       Payload: {"x": int, "y": int}
       Description: Clicks at specified x, y coordinates on the desktop.
       
    7. "type_text"
       Payload: {"text": "string"}
       Description: Types text at the current cursor position.
       
    8. "press_hotkey"
       Payload: {"keys": ["string list of key names"]}
       Description: Presses a combination of hotkeys on the physical keyboard (e.g., ["win"], ["ctrl", "c"]).
       
    9. "focus_window"
       Payload: {"title": "string (window title)"}
       Description: Focuses on a window with the specified title.

    10. "open_app"
       Payload: {"target": "string (e.g., 'notepad', 'calc', 'cmd', 'code' for VS Code)"}
       Description: Opens a local native desktop application. Do NOT use this to open websites or URLs. If the user wants to open a website, you MUST use the `browser_navigate` tool instead.
       
    11. "browser_navigate"
       Payload: {"url": "string (e.g., 'https://linkedin.com/login')"}
       Description: Opens a physical, visible browser window to the target URL and waits for it to load. Use this whenever the user says "open [website]" (e.g. "open linkedin", "open youtube") or asks to search/navigate the web.
       
    12. "browser_click"
       Payload: {"selector": "string (CSS, XPath, or text, e.g. 'text=Sign In')"}
       Description: Waits up to 10s for the element to be actionable, then clicks it. If the selector is not found, JARVIS will automatically escalate to the Vision AI for pixel-level screen interaction.
       
    13. "browser_type"
       Payload: {"selector": "string (e.g. 'input[type=\"email\"]')", "text": "string"}
       Description: Locates the specific input field, focuses it, clears contents, and types the text payload. If the field cannot be located, JARVIS will automatically escalate to the Vision AI.
       
    14. "browser_scrape_text"
       Payload: {"selector": "string (default is 'body')"}
       Description: Pulls the visible raw text from the specified container. Crucial for verifying states (e.g., check for a captcha, or verify login success).

    15. "scan_and_analyze_local_resumes"
       Payload: {"folder_path": "string (default 'C:\\Users\\mass0\\OneDrive\\Desktop\\jarvish_os\\resumes')", "job_description_text": "string"}
       Description: Memory Mesh Document Ingestion. Scans local resume PDFs/text files, runs a rapid token-comparison matrix against the given job description, and returns the absolute path of the winning resume file alongside a 2-sentence justification.

    16. "get_user_profile_context"
       Payload: {"field_category": "string (e.g., 'personal_info', 'professional_history', 'cover_letter_matrices', or 'all')"}
       Description: Natively reads user_profile.json in O(1) time and returns structural fields for job application form-filling operations.

    17. "ask_user_for_clarification"
       Payload: {"question": "string (The concise conversational question to ask)", "context": "string (Why you are blocked)"}
       Description: Universal Clarification Engine. If you lack the required context, or if the graphical interface prevents you from completing a step, you MUST halt execution and call this tool to ask the user for guidance.
    """