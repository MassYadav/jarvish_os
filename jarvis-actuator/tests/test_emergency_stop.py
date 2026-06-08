import pytest

from src.models.schemas import ActionContext
from src.security.emergency_stop import (
    ActuatorLockedError,
    ActuatorStoppedError,
    emergency_stop_manager,
)


def test_global_stop_engages_stop_and_lock(isolated_runtime):
    context = ActionContext(requested_by="tester")

    audit_id = emergency_stop_manager.engage_global_stop("test stop", context)
    status = emergency_stop_manager.status()

    assert audit_id
    assert status["emergency_stop_enabled"] is True
    assert status["actuator_locked"] is True
    assert status["emergency_stop"]["reason"] == "test stop"


def test_clear_global_stop_keeps_actuator_locked(isolated_runtime):
    context = ActionContext(requested_by="tester")

    emergency_stop_manager.engage_global_stop("test stop", context)
    emergency_stop_manager.clear_global_stop("clear stop", context)
    status = emergency_stop_manager.status()

    assert status["emergency_stop_enabled"] is False
    assert status["actuator_locked"] is True


def test_unlock_requires_cleared_global_stop(isolated_runtime):
    context = ActionContext(requested_by="tester")
    emergency_stop_manager.engage_global_stop("test stop", context)

    with pytest.raises(ActuatorStoppedError):
        emergency_stop_manager.unlock_actuator("unlock blocked", context)


def test_assert_ready_blocks_locked_actuator(isolated_runtime):
    context = ActionContext(requested_by="tester")
    emergency_stop_manager.lock_actuator("maintenance", context)

    with pytest.raises(ActuatorLockedError):
        emergency_stop_manager.assert_ready()


def test_assert_ready_after_clear_and_unlock(isolated_runtime):
    context = ActionContext(requested_by="tester")

    emergency_stop_manager.engage_global_stop("test stop", context)
    emergency_stop_manager.clear_global_stop("clear stop", context)
    emergency_stop_manager.unlock_actuator("resume", context)

    emergency_stop_manager.assert_ready()
    assert emergency_stop_manager.status()["actuator_locked"] is False
