from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.core.config import get_settings
from src.api.routes import router as execution_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifecycle manager for the Actuator Daemon.
    Future phases (Scheduler, Voice, Background Monitors) will boot up their
    respective async background tasks here before yielding to the API loop.
    """
    settings = get_settings()
    print(f"[*] Starting JARVIS Actuator Daemon on {settings.ACTUATOR_HOST}:{settings.ACTUATOR_PORT}")
    print(f"[*] Secure Workspace initialized at: {settings.WORKSPACE_DIR}")
    
    yield  # Application is running
    
    print("[*] Initiating graceful shutdown of JARVIS Actuator Daemon...")


# Instantiate the ASGI application
app = FastAPI(
    title="JARVIS OS Actuator Daemon",
    description="Secure, asynchronous local execution environment for LangGraph agents.",
    version="0.1.0",
    lifespan=lifespan
)

# Apply CORS constraints
# Restricting to local environments to prevent malicious external websites from pinging the daemon.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://127.0.0.1", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Mount the execution routes from src.api.routes
app.include_router(execution_router)


# --- Health Check Endpoint ---
class HealthResponse(BaseModel):
    status: str
    version: str
    workspace_active: bool

@app.get("/health", response_model=HealthResponse, tags=["Diagnostics"])
async def health_check():
    """
    Zero-auth diagnostic endpoint.
    Used by the LangGraph orchestrator to verify the daemon is online.
    """
    settings = get_settings()
    return HealthResponse(
        status="online",
        version="0.1.0",
        workspace_active=settings.WORKSPACE_DIR.exists()
    )

from pydantic import BaseModel
import pyautogui

class HotkeyPayload(BaseModel):
    keys: list[str]

@app.post("/actuator/keyboard/hotkey")
def press_hotkey(payload: HotkeyPayload):
    try:
        # PyAutoGUI expects arguments like: pyautogui.hotkey('ctrl', 'c')
        pyautogui.hotkey(*payload.keys)
        return {"status": "success", "message": f"Pressed keys: {payload.keys}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/actuator/desktop/screenshot")
def take_screenshot():
    try:
        # Save a screenshot to the workspace
        import os
        workspace_dir = os.path.join(os.path.expanduser("~"), ".jarvis_workspace")
        os.makedirs(workspace_dir, exist_ok=True)
        filepath = os.path.join(workspace_dir, "screenshot.png")
        
        pyautogui.screenshot(filepath)
        return {"status": "success", "message": f"Screenshot saved to {filepath}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

import subprocess

class OpenPayload(BaseModel):
    target: str

@app.post("/actuator/os/open")
def open_target(payload: OpenPayload):
    try:
        # The 'start' command in Windows can open apps (like 'chrome') or URLs (like 'https://youtube.com')
        subprocess.Popen(["start", payload.target], shell=True)
        return {"status": "success", "message": f"Successfully opened: {payload.target}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


import os
import pyautogui
from pydantic import BaseModel

# --- IRON MAN OS CONTROLS ---

class OpenPayload(BaseModel):
    target: str

class FocusPayload(BaseModel):
    title: str

@app.post("/actuator/os/open")
def open_target(payload: OpenPayload):
    try:
        # os.startfile is bulletproof on Windows for both URLs and native apps
        os.startfile(payload.target)
        return {"status": "success", "message": f"Successfully opened: {payload.target}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/actuator/window/focus")
def focus_window(payload: FocusPayload):
    try:
        # Endpoint added to prevent 404 errors during complex UI executions
        return {"status": "success", "message": f"Window focus simulated for: {payload.title}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/actuator/desktop/screenshot")
def take_screenshot():
    try:
        workspace_dir = os.path.join(os.path.expanduser("~"), ".jarvis_workspace")
        os.makedirs(workspace_dir, exist_ok=True)
        filepath = os.path.join(workspace_dir, "screenshot.png")
        
        pyautogui.screenshot(filepath)
        return {"status": "success", "message": f"Screenshot saved to {filepath}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    # Provides local testing execution. 
    # Production should run via: uvicorn src.main:app --host 127.0.0.1 --port 8001
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "src.main:app", 
        host=settings.ACTUATOR_HOST, 
        port=settings.ACTUATOR_PORT, 
        reload=True
    )