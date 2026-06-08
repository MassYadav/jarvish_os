from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.models.schemas import ActionContext
from src.security.config import settings
from src.security.emergency_stop import emergency_stop_manager


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    action: str
    message: str
    risk_score: int
    requires_approval: bool
    metadata: dict[str, Any] = field(default_factory=dict)


class ActuatorPolicy:
    def evaluate_action(
        self,
        *,
        action: str,
        context: ActionContext,
        metadata: dict[str, Any] | None = None,
    ) -> PolicyDecision:
        emergency_stop_manager.assert_ready()

        action_metadata = metadata or {}
        risk_score = self._effective_risk_score(action, context)
        requires_approval = context.requires_approval or risk_score >= settings.approval_risk_threshold

        if action == "keyboard.type" and settings.force_approval_for_typing:
            requires_approval = True
        if action == "process.launch" and settings.force_approval_for_process_launch:
            requires_approval = True
        if action.startswith("clipboard.") and settings.force_approval_for_clipboard:
            requires_approval = True

        sensitive_reason = self._sensitive_window_reason(action_metadata)
        if sensitive_reason:
            return PolicyDecision(
                allowed=False,
                action=action,
                message=sensitive_reason,
                risk_score=max(risk_score, 90),
                requires_approval=True,
                metadata=action_metadata,
            )

        return PolicyDecision(
            allowed=not requires_approval,
            action=action,
            message=(
                "Action requires human approval"
                if requires_approval
                else "Action allowed by actuator policy"
            ),
            risk_score=risk_score,
            requires_approval=requires_approval,
            metadata=action_metadata,
        )

    def evaluate_process_launch(
        self,
        *,
        application: str,
        context: ActionContext,
        metadata: dict[str, Any] | None = None,
    ) -> PolicyDecision:
        emergency_stop_manager.assert_ready()

        normalized_app = self._normalize_application(application)
        action_metadata = {"application": application, "normalized_application": normalized_app}
        action_metadata.update(metadata or {})

        if normalized_app in settings.denied_applications:
            return PolicyDecision(
                allowed=False,
                action="process.launch",
                message=f"Application is denied by policy: {normalized_app}",
                risk_score=max(context.risk_score, 100),
                requires_approval=True,
                metadata=action_metadata,
            )

        if normalized_app not in settings.allowed_applications:
            return PolicyDecision(
                allowed=False,
                action="process.launch",
                message=f"Application is not allowlisted: {normalized_app}",
                risk_score=max(context.risk_score, 85),
                requires_approval=True,
                metadata=action_metadata,
            )

        risk_score = max(context.risk_score, 50)
        requires_approval = (
            context.requires_approval
            or settings.force_approval_for_process_launch
            or risk_score >= settings.approval_risk_threshold
        )

        return PolicyDecision(
            allowed=not requires_approval,
            action="process.launch",
            message=(
                "Process launch requires human approval"
                if requires_approval
                else "Process launch allowed by policy"
            ),
            risk_score=risk_score,
            requires_approval=requires_approval,
            metadata=action_metadata,
        )

    def _effective_risk_score(self, action: str, context: ActionContext) -> int:
        base_scores = {
            "window.focus": 15,
            "window.list": 5,
            "mouse.move": 20,
            "mouse.click": 35,
            "keyboard.type": 45,
            "keyboard.hotkey": 55,
            "screenshot.capture": 25,
            "clipboard.read": 60,
            "clipboard.write": 65,
        }
        return max(context.risk_score, base_scores.get(action, 40))

    def _normalize_application(self, application: str) -> str:
        value = application.strip().strip('"').strip("'")
        if not value:
            return ""
        return Path(value).name.lower()

    def _sensitive_window_reason(self, metadata: dict[str, Any]) -> str | None:
        window_title = str(metadata.get("active_window_title") or metadata.get("window_title") or "")
        lowered_title = window_title.lower()
        for term in settings.sensitive_window_terms:
            if term in lowered_title:
                return f"Sensitive window blocked by policy: {term}"
        return None


actuator_policy = ActuatorPolicy()
