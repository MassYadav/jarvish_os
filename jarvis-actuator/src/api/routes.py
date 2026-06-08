from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel, Field

from src.controllers.actuator_controller import (
    ActuatorControllerError,
    actuator_controller,
)
from src.models.schemas import (
    ActionContext,
    ActionResponse,
    HealthResponse,
    KeyboardHotkeyRequest,
    KeyboardTypeRequest,
    MouseClickRequest,
    MouseMoveRequest,
    ProcessLaunchRequest,
    Region,
    ScreenshotCaptureRequest,
    ScreenshotMode,
    ScreenshotResponse,
    WindowFocusRequest,
    WindowListResponse,
)

router = APIRouter(prefix="/actuator", tags=["actuator"])


class WindowListRequest(BaseModel):
    context: ActionContext = Field(default_factory=ActionContext)


@router.post("/window/focus", response_model=ActionResponse)
def focus_window(request: WindowFocusRequest) -> ActionResponse:
    try:
        return actuator_controller.focus_window(request)
    except ActuatorControllerError as exc:
        raise _controller_http_error(exc) from exc


@router.post("/window/list", response_model=WindowListResponse)
def list_windows(
    request: WindowListRequest | None = Body(default=None),
) -> WindowListResponse:
    try:
        context = request.context if request else ActionContext()
        return actuator_controller.list_windows(context)
    except ActuatorControllerError as exc:
        raise _controller_http_error(exc) from exc


@router.post("/mouse/click", response_model=ActionResponse)
def click_mouse(request: MouseClickRequest) -> ActionResponse:
    try:
        return actuator_controller.click_mouse(request)
    except ActuatorControllerError as exc:
        raise _controller_http_error(exc) from exc


@router.post("/mouse/move", response_model=ActionResponse)
def move_mouse(request: MouseMoveRequest) -> ActionResponse:
    try:
        return actuator_controller.move_mouse(request)
    except ActuatorControllerError as exc:
        raise _controller_http_error(exc) from exc


@router.post("/keyboard/type", response_model=ActionResponse)
def type_text(request: KeyboardTypeRequest) -> ActionResponse:
    try:
        return actuator_controller.type_text(request)
    except ActuatorControllerError as exc:
        raise _controller_http_error(exc) from exc


@router.post("/keyboard/hotkey", response_model=ActionResponse)
def press_hotkey(request: KeyboardHotkeyRequest) -> ActionResponse:
    try:
        return actuator_controller.press_hotkey(request)
    except ActuatorControllerError as exc:
        raise _controller_http_error(exc) from exc


@router.post("/process/launch", response_model=ActionResponse)
def launch_application(request: ProcessLaunchRequest) -> ActionResponse:
    try:
        return actuator_controller.launch_application(request)
    except ActuatorControllerError as exc:
        raise _controller_http_error(exc) from exc


@router.get("/screenshot", response_model=ScreenshotResponse)
def capture_screenshot(
    mode: ScreenshotMode = Query(default=ScreenshotMode.FULL),
    persist: bool = Query(default=True),
    x: int | None = Query(default=None, ge=0),
    y: int | None = Query(default=None, ge=0),
    width: int | None = Query(default=None, gt=0),
    height: int | None = Query(default=None, gt=0),
    execution_id: str | None = Query(default=None, min_length=1, max_length=128),
    requested_by: str = Query(default="jarvis", min_length=1, max_length=128),
    source: str = Query(default="langgraph", min_length=1, max_length=128),
    risk_score: int = Query(default=0, ge=0, le=100),
    requires_approval: bool = Query(default=False),
    audit_tags: list[str] | None = Query(default=None),
) -> ScreenshotResponse:
    context_payload = {
        "requested_by": requested_by,
        "source": source,
        "risk_score": risk_score,
        "requires_approval": requires_approval,
        "audit_tags": audit_tags or [],
    }
    if execution_id:
        context_payload["execution_id"] = execution_id

    region = _build_region(mode=mode, x=x, y=y, width=width, height=height)
    request = ScreenshotCaptureRequest(
        mode=mode,
        region=region,
        persist=persist,
        context=ActionContext(**context_payload),
    )

    try:
        return actuator_controller.capture_screenshot(request)
    except ActuatorControllerError as exc:
        raise _controller_http_error(exc) from exc


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return actuator_controller.health()


def _build_region(
    *,
    mode: ScreenshotMode,
    x: int | None,
    y: int | None,
    width: int | None,
    height: int | None,
) -> Region | None:
    if mode != ScreenshotMode.REGION:
        return None

    if x is None or y is None or width is None or height is None:
        raise HTTPException(
            status_code=400,
            detail="Region screenshots require x, y, width, and height query parameters",
        )

    return Region(x=x, y=y, width=width, height=height)


def _controller_http_error(exc: ActuatorControllerError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail={"message": str(exc), "audit_id": exc.audit_id},
    )
