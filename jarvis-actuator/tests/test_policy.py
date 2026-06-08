from src.models.schemas import ActionContext
from src.security.config import settings
from src.security.policy import actuator_policy


def test_denied_application_is_blocked(isolated_runtime):
    context = ActionContext(risk_score=0)

    decision = actuator_policy.evaluate_process_launch(
        application="powershell.exe",
        context=context,
    )

    assert decision.allowed is False
    assert decision.requires_approval is True
    assert decision.risk_score == 100


def test_non_allowlisted_application_is_blocked(isolated_runtime):
    context = ActionContext(risk_score=0)

    decision = actuator_policy.evaluate_process_launch(
        application="unknown-tool.exe",
        context=context,
    )

    assert decision.allowed is False
    assert decision.requires_approval is True
    assert "not allowlisted" in decision.message


def test_allowlisted_application_can_require_approval(isolated_runtime, monkeypatch):
    monkeypatch.setattr(settings, "force_approval_for_process_launch", True)
    context = ActionContext(risk_score=10)

    decision = actuator_policy.evaluate_process_launch(
        application="notepad.exe",
        context=context,
    )

    assert decision.allowed is False
    assert decision.requires_approval is True
    assert decision.risk_score >= 50


def test_sensitive_window_term_blocks_action(isolated_runtime):
    context = ActionContext(risk_score=10)

    decision = actuator_policy.evaluate_action(
        action="mouse.click",
        context=context,
        metadata={"active_window_title": "Password Manager"},
    )

    assert decision.allowed is False
    assert decision.requires_approval is True
    assert decision.risk_score >= 90


def test_low_risk_window_list_is_allowed(isolated_runtime):
    context = ActionContext(risk_score=0)

    decision = actuator_policy.evaluate_action(
        action="window.list",
        context=context,
        metadata={},
    )

    assert decision.allowed is True
    assert decision.requires_approval is False
    assert decision.risk_score == 5


def test_high_risk_action_requires_approval(isolated_runtime):
    context = ActionContext(risk_score=settings.approval_risk_threshold)

    decision = actuator_policy.evaluate_action(
        action="mouse.move",
        context=context,
        metadata={},
    )

    assert decision.allowed is False
    assert decision.requires_approval is True
