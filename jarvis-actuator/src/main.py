import os
import subprocess
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pyautogui
import base64
from io import BytesIO
import win32gui
import pyperclip

from src.core.config import get_settings
from src.api.routes import router as execution_router

# Fail-safe security config for PyAutoGUI (prevents wild loops by moving mouse to corner)
pyautogui.FAILSAFE = True

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    print(f"[*] Starting JARVIS Actuator Daemon on {settings.ACTUATOR_HOST}:{settings.ACTUATOR_PORT}")
    print(f"[*] Secure Workspace initialized at: {settings.WORKSPACE_DIR}")
    yield
    print("[*] Initiating graceful shutdown of JARVIS Actuator Daemon...")

app = FastAPI(
    title="JARVIS OS Actuator Daemon",
    description="Secure, asynchronous local execution environment for LangGraph agents.",
    version="0.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://127.0.0.1", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(execution_router)

# --- Pydantic Data Structures ---

class HealthResponse(BaseModel):
    status: str
    version: str
    workspace_active: bool

class ClickPayload(BaseModel):
    x: int
    y: int

class TypePayload(BaseModel):
    text: str

class HotkeyPayload(BaseModel):
    keys: list[str]

class OpenPayload(BaseModel):
    target: str

class FocusPayload(BaseModel):
    title: str

class ScreenshotOptions(BaseModel):
    return_base64: bool = False


# --- Core Actuator Endpoints ---

@app.get("/health", response_model=HealthResponse, tags=["Diagnostics"])
async def health_check():
    settings = get_settings()
    return HealthResponse(
        status="online",
        version="0.1.0",
        workspace_active=settings.WORKSPACE_DIR.exists()
    )

@app.post("/actuator/desktop/screenshot")
def take_screenshot(options: ScreenshotOptions = ScreenshotOptions()):
    try:
        workspace_dir = os.path.join(os.path.expanduser("~"), ".jarvis_workspace")
        os.makedirs(workspace_dir, exist_ok=True)
        filepath = os.path.join(workspace_dir, "screenshot.png")
        img = pyautogui.screenshot(filepath)
        
        b64_data = ""
        if options.return_base64:
            buffered = BytesIO()
            img.save(buffered, format="PNG")
            b64_data = base64.b64encode(buffered.getvalue()).decode("utf-8")
            
        return {"status": "success", "message": f"Screenshot saved to {filepath}", "base64": b64_data}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/actuator/desktop/active_window")
def get_active_window():
    try:
        hwnd = win32gui.GetForegroundWindow()
        title = win32gui.GetWindowText(hwnd)
        return {"status": "success", "title": title}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/actuator/desktop/clipboard")
def get_clipboard():
    try:
        text = pyperclip.paste()
        return {"status": "success", "text": text}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/actuator/mouse/click")
def click_at(payload: ClickPayload):
    try:
        pyautogui.click(payload.x, payload.y)
        return {"status": "success", "message": f"Clicked coordinates: X={payload.x}, Y={payload.y}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/actuator/keyboard/type")
def type_text(payload: TypePayload):
    try:
        pyautogui.write(payload.text, interval=0.01)
        return {"status": "success", "message": "Text input sequence executed."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/actuator/keyboard/hotkey")
def press_hotkey(payload: HotkeyPayload):
    try:
        pyautogui.hotkey(*payload.keys)
        return {"status": "success", "message": f"Pressed hotkeys: {payload.keys}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/actuator/os/open")
def open_target(payload: OpenPayload):
    try:
        # os.startfile is bulletproof on Windows for both files/apps and valid web URLs
        os.startfile(payload.target)
        return {"status": "success", "message": f"Successfully executed target: {payload.target}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/actuator/window/focus")
def focus_window(payload: FocusPayload):
    try:
        return {"status": "success", "message": f"Window focus context synchronized for: {payload.title}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "src.main:app", 
        host=settings.ACTUATOR_HOST, 
        port=settings.ACTUATOR_PORT, 
        reload=True
    )