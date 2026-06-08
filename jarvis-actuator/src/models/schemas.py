from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class MouseButton(StrEnum):
    LEFT = "left"
    RIGHT = "right"
    MIDDLE = "middle"


class ScreenshotMode(StrEnum):
    FULL = "full"
    ACTIVE_WINDOW = "active_window"
    REGION = "region"


class ActionContext(BaseModel):
    execution_id: str = Field(default_factory=lambda: str(uuid4()))
    requested_by: str = Field(default="jarvis", min_length=1, max_length=128)
    source: str = Field(default="langgraph", min_length=1, max_length=128)
    risk_score: int = Field(default=0, ge=0, le=100)
    requires_approval: bool = False
    audit_tags: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("audit_tags")
    @classmethod
    def normalize_audit_tags(cls, tags: list[str]) -> list[str]:
        return [tag.strip().lower() for tag in tags if tag.strip()]


class Region(BaseModel):
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class WindowFocusRequest(BaseModel):
    title: str = Field(min_length=1, max_length=256)
    exact_match: bool = False
    context: ActionContext = Field(default_factory=ActionContext)


class WindowInfo(BaseModel):
    title: str
    is_active: bool
    is_minimized: bool
    left: int | None = None
    top: int | None = None
    width: int | None = None
    height: int | None = None
    handle: int | None = None
    process_name: str | None = None


class MouseMoveRequest(BaseModel):
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    duration_seconds: float = Field(default=0.0, ge=0.0, le=10.0)
    context: ActionContext = Field(default_factory=ActionContext)


class MouseClickRequest(BaseModel):
    x: int | None = Field(default=None, ge=0)
    y: int | None = Field(default=None, ge=0)
    button: MouseButton = MouseButton.LEFT
    clicks: int = Field(default=1, ge=1, le=5)
    interval_seconds: float = Field(default=0.0, ge=0.0, le=5.0)
    context: ActionContext = Field(default_factory=ActionContext)


class KeyboardTypeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=10_000)
    interval_seconds: float = Field(default=0.0, ge=0.0, le=1.0)
    context: ActionContext = Field(default_factory=ActionContext)


class KeyboardHotkeyRequest(BaseModel):
    keys: list[str] = Field(min_length=1, max_length=6)
    context: ActionContext = Field(default_factory=ActionContext)

    @field_validator("keys")
    @classmethod
    def normalize_keys(cls, keys: list[str]) -> list[str]:
        return [key.strip().lower() for key in keys if key.strip()]


class ProcessLaunchRequest(BaseModel):
    application: str = Field(min_length=1, max_length=256)
    args: list[str] = Field(default_factory=list, max_length=32)
    working_directory: str | None = Field(default=None, max_length=512)
    context: ActionContext = Field(default_factory=ActionContext)


class ScreenshotCaptureRequest(BaseModel):
    mode: ScreenshotMode = ScreenshotMode.FULL
    region: Region | None = None
    persist: bool = True
    context: ActionContext = Field(default_factory=ActionContext)


class ScreenshotMetadata(BaseModel):
    screenshot_id: str
    execution_id: str
    mode: ScreenshotMode
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    path: str | None = None
    created_at: str
    active_window_title: str | None = None
    region: Region | None = None
    labels: dict[str, str] = Field(default_factory=dict)


class ActionResponse(BaseModel):
    success: bool
    action: str
    execution_id: str
    risk_score: int = Field(ge=0, le=100)
    requires_approval: bool
    audit_id: str
    message: str
    data: dict[str, Any] = Field(default_factory=dict)


class WindowListResponse(BaseModel):
    success: bool = True
    execution_id: str
    audit_id: str
    windows: list[WindowInfo]


class ScreenshotResponse(BaseModel):
    success: bool = True
    audit_id: str
    metadata: ScreenshotMetadata
    image_base64: str


class HealthResponse(BaseModel):
    status: str
    service: str
    emergency_stop_enabled: bool
    actuator_locked: bool
    screenshot_persistence_enabled: bool

