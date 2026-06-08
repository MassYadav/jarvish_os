from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any
import json

from src.models.schemas import ActionContext
from src.security.audit import audit_logger
from src.security.config import settings


class ActuatorStoppedError(RuntimeError):
    """Raised when the global emergency stop is engaged."""


class ActuatorLockedError(RuntimeError):
    """Raised when the actuator is administratively locked."""


class EmergencyStopManager:
    def __init__(
        self,
        emergency_stop_file: Path | None = None,
        lock_state_file: Path | None = None,
    ) -> None:
        self.emergency_stop_file = emergency_stop_file or settings.emergency_stop_file
        self.lock_state_file = lock_state_file or settings.lock_state_file
        self._state_lock = RLock()

        if settings.start_locked and not self.lock_state_file.exists():
            startup_context = ActionContext(
                requested_by="system",
                source="actuator-startup",
                requires_approval=False,
                audit_tags=["startup", "lock"],
            )
            self.lock_actuator("Actuator configured to start locked", startup_context)

    def engage_global_stop(
        self,
        reason: str,
        context: ActionContext | None = None,
    ) -> str:
        action_context = context or self._system_context("emergency-stop")
        payload = self._marker_payload(reason, action_context)

        with self._state_lock:
            self._write_marker(self.emergency_stop_file, payload)
            self._write_marker(self.lock_state_file, payload)

        return audit_logger.record(
            action="emergency_stop.engage",
            context=action_context,
            allowed=True,
            message=reason,
            metadata=self.status(),
        )

    def clear_global_stop(
        self,
        reason: str,
        context: ActionContext | None = None,
    ) -> str:
        action_context = context or self._system_context("emergency-stop-clear")

        with self._state_lock:
            self._remove_marker(self.emergency_stop_file)

        return audit_logger.record(
            action="emergency_stop.clear",
            context=action_context,
            allowed=True,
            message=reason,
            metadata=self.status(),
        )

    def lock_actuator(
        self,
        reason: str,
        context: ActionContext | None = None,
    ) -> str:
        action_context = context or self._system_context("actuator-lock")

        with self._state_lock:
            self._write_marker(self.lock_state_file, self._marker_payload(reason, action_context))

        return audit_logger.record(
            action="actuator.lock",
            context=action_context,
            allowed=True,
            message=reason,
            metadata=self.status(),
        )

    def unlock_actuator(
        self,
        reason: str,
        context: ActionContext | None = None,
    ) -> str:
        action_context = context or self._system_context("actuator-unlock")

        if self.is_emergency_stopped():
            audit_id = audit_logger.record(
                action="actuator.unlock",
                context=action_context,
                allowed=False,
                message="Cannot unlock actuator while global emergency stop is engaged",
                metadata=self.status(),
            )
            raise ActuatorStoppedError(f"Emergency stop must be cleared first. audit_id={audit_id}")

        with self._state_lock:
            self._remove_marker(self.lock_state_file)

        return audit_logger.record(
            action="actuator.unlock",
            context=action_context,
            allowed=True,
            message=reason,
            metadata=self.status(),
        )

    def assert_ready(self) -> None:
        if self.is_emergency_stopped():
            raise ActuatorStoppedError("Global emergency stop is engaged")
        if self.is_locked():
            raise ActuatorLockedError("Actuator is locked")

    def is_emergency_stopped(self) -> bool:
        return self.emergency_stop_file.exists()

    def is_locked(self) -> bool:
        return self.lock_state_file.exists()

    def status(self) -> dict[str, Any]:
        return {
            "emergency_stop_enabled": self.is_emergency_stopped(),
            "actuator_locked": self.is_locked(),
            "emergency_stop": self._read_marker(self.emergency_stop_file),
            "lock_state": self._read_marker(self.lock_state_file),
        }

    def _marker_payload(self, reason: str, context: ActionContext) -> dict[str, Any]:
        return {
            "reason": reason.strip() or "No reason supplied",
            "created_at": datetime.now(UTC).isoformat(),
            "execution_id": context.execution_id,
            "requested_by": context.requested_by,
            "source": context.source,
            "risk_score": context.risk_score,
            "requires_approval": context.requires_approval,
            "audit_tags": context.audit_tags,
        }

    def _write_marker(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")

    def _remove_marker(self, path: Path) -> None:
        if path.exists():
            path.unlink()

    def _read_marker(self, path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"error": "Marker file is not valid JSON", "path": str(path)}

    def _system_context(self, tag: str) -> ActionContext:
        return ActionContext(
            requested_by="system",
            source="actuator-security",
            requires_approval=False,
            audit_tags=[tag],
        )


emergency_stop_manager = EmergencyStopManager()
