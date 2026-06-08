from __future__ import annotations

from typing import Any

from src.models.schemas import (
    ActionContext,
    ActionResponse,
    HealthResponse,
    KeyboardHotkeyRequest,
    KeyboardTypeRequest,
    MouseClickRequest,
    MouseMoveRequest,
    ProcessLaunchRequest,
    ScreenshotCaptureRequest,
    ScreenshotResponse,
    WindowFocusRequest,
    WindowListResponse,
)
from src.security.audit import audit_logger
from src.security.config import settings
from src.security.emergency_stop import (
    ActuatorLockedError,
    ActuatorStoppedError,
    emergency_stop_manager,
)
from src.security.policy import PolicyDecision, actuator_policy
from src.services.keyboard_service import KeyboardServiceError, keyboard_service
from src.services.mouse_service import MouseServiceError, mouse_service
from src.services.process_service import ProcessServiceError, process_service
from src.services.screenshot_service import ScreenshotServiceError, screenshot_service
from src.services.window_service import WindowServiceError, window_service


class ActuatorControllerError(RuntimeError):
    def __init__(self, message: str, *, audit_id: str, status_code: int = 500) -> None:
        super().__init__(message)
        self.audit_id = audit_id
        self.status_code = status_code


class ActuatorController:
    def focus_window(self, request: WindowFocusRequest) -> ActionResponse:
        action = "window.focus"
        metadata = {"window_title": request.title, "exact_match": request.exact_match}
        decision = self._evaluate_action(action, request.context, metadata)
        if not decision.allowed:
            return self._blocked_action_response(decision, request.context)

        try:
            window = window_service.focus_window(
                title=request.title,
                exact_match=request.exact_match,
            )
            return self._successful_action_response(
                decision=decision,
                context=request.context,
                message="Window focused",
                data={"window": window.model_dump()},
            )
        except WindowServiceError as exc:
            return self._failed_action_response(decision, request.context, str(exc))

    def list_windows(self, context: ActionContext) -> WindowListResponse:
        action = "window.list"
        decision = self._evaluate_action(action, context, {})
        if not decision.allowed:
            self._raise_blocked(decision, context)

        try:
            windows = window_service.list_windows()
        except WindowServiceError as exc:
            audit_id = audit_logger.record(
                action=action,
                context=context,
                allowed=False,
                message=str(exc),
                error=str(exc),
            )
            raise ActuatorControllerError(str(exc), audit_id=audit_id) from exc

        audit_id = audit_logger.record(
            action=action,
            context=context,
            allowed=True,
            message="Windows listed",
            metadata={"window_count": len(windows)},
        )
        return WindowListResponse(
            success=True,
            execution_id=context.execution_id,
            audit_id=audit_id,
            windows=windows,
        )

    def move_mouse(self, request: MouseMoveRequest) -> ActionResponse:
        action = "mouse.move"
        metadata = self._active_window_metadata()
        metadata.update(
            {
                "x": request.x,
                "y": request.y,
                "duration_seconds": request.duration_seconds,
            }
        )
        decision = self._evaluate_action(action, request.context, metadata)
        if not decision.allowed:
            return self._blocked_action_response(decision, request.context)

        try:
            result = mouse_service.move(
                x=request.x,
                y=request.y,
                duration_seconds=request.duration_seconds,
            )
            return self._successful_action_response(
                decision=decision,
                context=request.context,
                message="Mouse moved",
                data=result,
            )
        except MouseServiceError as exc:
            return self._failed_action_response(decision, request.context, str(exc))

    def click_mouse(self, request: MouseClickRequest) -> ActionResponse:
        action = "mouse.click"
        metadata = self._active_window_metadata()
        metadata.update(
            {
                "x": request.x,
                "y": request.y,
                "button": request.button.value,
                "clicks": request.clicks,
                "interval_seconds": request.interval_seconds,
            }
        )
        decision = self._evaluate_action(action, request.context, metadata)
        if not decision.allowed:
            return self._blocked_action_response(decision, request.context)

        try:
            result = mouse_service.click(
                x=request.x,
                y=request.y,
                button=request.button,
                clicks=request.clicks,
                interval_seconds=request.interval_seconds,
            )
            return self._successful_action_response(
                decision=decision,
                context=request.context,
                message="Mouse clicked",
                data=result,
            )
        except MouseServiceError as exc:
            return self._failed_action_response(decision, request.context, str(exc))

    def type_text(self, request: KeyboardTypeRequest) -> ActionResponse:
        action = "keyboard.type"
        metadata = self._active_window_metadata()
        metadata.update({"characters": len(request.text)})
        decision = self._evaluate_action(action, request.context, metadata)
        if not decision.allowed:
            return self._blocked_action_response(decision, request.context)

        try:
            result = keyboard_service.type_text(
                text=request.text,
                interval_seconds=request.interval_seconds,
            )
            return self._successful_action_response(
                decision=decision,
                context=request.context,
                message="Text typed",
                data=result,
            )
        except KeyboardServiceError as exc:
            return self._failed_action_response(decision, request.context, str(exc))

    def press_hotkey(self, request: KeyboardHotkeyRequest) -> ActionResponse:
        action = "keyboard.hotkey"
        metadata = self._active_window_metadata()
        metadata.update({"keys": request.keys})
        decision = self._evaluate_action(action, request.context, metadata)
        if not decision.allowed:
            return self._blocked_action_response(decision, request.context)

        try:
            result = keyboard_service.press_hotkey(keys=request.keys)
            return self._successful_action_response(
                decision=decision,
                context=request.context,
                message="Hotkey pressed",
                data=result,
            )
        except KeyboardServiceError as exc:
            return self._failed_action_response(decision, request.context, str(exc))

    def launch_application(self, request: ProcessLaunchRequest) -> ActionResponse:
        decision = actuator_policy.evaluate_process_launch(
            application=request.application,
            context=request.context,
            metadata={
                "args_count": len(request.args),
                "working_directory": request.working_directory,
            },
        )
        if not decision.allowed:
            return self._blocked_action_response(decision, request.context)

        try:
            result = process_service.launch(
                application=request.application,
                args=request.args,
                working_directory=request.working_directory,
            )
            return self._successful_action_response(
                decision=decision,
                context=request.context,
                message="Application launched",
                data=result,
            )
        except ProcessServiceError as exc:
            return self._failed_action_response(decision, request.context, str(exc))

    def capture_screenshot(self, request: ScreenshotCaptureRequest) -> ScreenshotResponse:
        action = "screenshot.capture"
        metadata: dict[str, Any] = {
            "mode": request.mode.value,
            "persist": request.persist,
            "region": request.region.model_dump() if request.region else None,
        }
        metadata.update(self._active_window_metadata())

        decision = self._evaluate_action(action, request.context, metadata)
        if not decision.allowed:
            self._raise_blocked(decision, request.context)

        try:
            capture = screenshot_service.capture(request)
        except ScreenshotServiceError as exc:
            audit_id = audit_logger.record(
                action=action,
                context=request.context,
                allowed=False,
                message=str(exc),
                metadata=metadata,
                error=str(exc),
            )
            raise ActuatorControllerError(str(exc), audit_id=audit_id) from exc

        audit_id = audit_logger.record(
            action=action,
            context=request.context,
            allowed=True,
            message="Screenshot captured",
            metadata=capture.metadata.model_dump(),
        )
        return ScreenshotResponse(
            success=True,
            audit_id=audit_id,
            metadata=capture.metadata,
            image_base64=capture.image_base64,
        )

    def health(self) -> HealthResponse:
        stop_status = emergency_stop_manager.status()
        emergency_stop_enabled = bool(stop_status["emergency_stop_enabled"])
        actuator_locked = bool(stop_status["actuator_locked"])

        if emergency_stop_enabled:
            status = "emergency_stopped"
        elif actuator_locked:
            status = "locked"
        else:
            status = "online"

        return HealthResponse(
            status=status,
            service=settings.service_name,
            emergency_stop_enabled=emergency_stop_enabled,
            actuator_locked=actuator_locked,
            screenshot_persistence_enabled=settings.screenshot_persistence_enabled,
        )

    def _evaluate_action(
        self,
        action: str,
        context: ActionContext,
        metadata: dict[str, Any],
    ) -> PolicyDecision:
        try:
            return actuator_policy.evaluate_action(
                action=action,
                context=context,
                metadata=metadata,
            )
        except (ActuatorStoppedError, ActuatorLockedError) as exc:
            audit_id = audit_logger.record(
                action=action,
                context=context,
                allowed=False,
                message=str(exc),
                metadata=metadata,
                error=str(exc),
            )
            raise ActuatorControllerError(str(exc), audit_id=audit_id, status_code=423) from exc

    def _successful_action_response(
        self,
        *,
        decision: PolicyDecision,
        context: ActionContext,
        message: str,
        data: dict[str, Any],
    ) -> ActionResponse:
        audit_id = audit_logger.record(
            action=decision.action,
            context=context,
            allowed=True,
            message=message,
            metadata={**decision.metadata, "result": data},
        )
        return ActionResponse(
            success=True,
            action=decision.action,
            execution_id=context.execution_id,
            risk_score=decision.risk_score,
            requires_approval=decision.requires_approval,
            audit_id=audit_id,
            message=message,
            data=data,
        )

    def _failed_action_response(
        self,
        decision: PolicyDecision,
        context: ActionContext,
        error: str,
    ) -> ActionResponse:
        audit_id = audit_logger.record(
            action=decision.action,
            context=context,
            allowed=False,
            message=error,
            metadata=decision.metadata,
            error=error,
        )
        return ActionResponse(
            success=False,
            action=decision.action,
            execution_id=context.execution_id,
            risk_score=decision.risk_score,
            requires_approval=decision.requires_approval,
            audit_id=audit_id,
            message=error,
            data={},
        )

    def _blocked_action_response(
        self,
        decision: PolicyDecision,
        context: ActionContext,
    ) -> ActionResponse:
        audit_id = audit_logger.record(
            action=decision.action,
            context=context,
            allowed=False,
            message=decision.message,
            metadata=decision.metadata,
        )
        return ActionResponse(
            success=False,
            action=decision.action,
            execution_id=context.execution_id,
            risk_score=decision.risk_score,
            requires_approval=decision.requires_approval,
            audit_id=audit_id,
            message=decision.message,
            data=decision.metadata,
        )

    def _raise_blocked(self, decision: PolicyDecision, context: ActionContext) -> None:
        audit_id = audit_logger.record(
            action=decision.action,
            context=context,
            allowed=False,
            message=decision.message,
            metadata=decision.metadata,
        )
        status_code = 403 if decision.requires_approval else 400
        raise ActuatorControllerError(
            decision.message,
            audit_id=audit_id,
            status_code=status_code,
        )

    def _active_window_metadata(self) -> dict[str, str]:
        try:
            title = window_service.get_active_window_title()
        except WindowServiceError:
            return {}
        return {"active_window_title": title} if title else {}


actuator_controller = ActuatorController()
