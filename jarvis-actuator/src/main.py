from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router
from src.security.audit import audit_logger
from src.security.config import settings
from src.security.emergency_stop import emergency_stop_manager


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings.audit_dir.mkdir(parents=True, exist_ok=True)
    settings.screenshot_dir.mkdir(parents=True, exist_ok=True)
    _configure_pyautogui()
    audit_logger.record(
        action="actuator.startup",
        context=emergency_stop_manager._system_context("startup"),
        allowed=True,
        message="Actuator service started",
        metadata={"environment": settings.environment, "platform": settings.platform_name},
    )
    yield
    audit_logger.record(
        action="actuator.shutdown",
        context=emergency_stop_manager._system_context("shutdown"),
        allowed=True,
        message="Actuator service stopped",
        metadata={"environment": settings.environment, "platform": settings.platform_name},
    )


app = FastAPI(
    title="JARVIS Desktop Automation Actuator",
    version="10.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


def _configure_pyautogui() -> None:
    try:
        import pyautogui
    except ImportError:
        return

    pyautogui.FAILSAFE = settings.pyautogui_failsafe
