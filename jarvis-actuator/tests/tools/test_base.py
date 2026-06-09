import pytest
from pydantic import ValidationError
from src.tools.base import ToolRequest, ExecutionResult


def test_tool_request_valid():
    """Verify that a properly formed tool request serializes correctly."""
    request = ToolRequest(
        tool_name="system_shell",
        parameters={"command": ["ls", "-la"]},
        timeout_override=30
    )
    
    assert request.tool_name == "system_shell"
    assert "command" in request.parameters
    assert request.timeout_override == 30


def test_tool_request_forbids_extra_fields():
    """Verify that unknown payload fields are aggressively rejected to prevent injection."""
    with pytest.raises(ValidationError) as excinfo:
        ToolRequest(
            tool_name="system_shell",
            parameters={},
            malicious_injection_field="drop tables"
        )
    
    assert "Extra inputs are not permitted" in str(excinfo.value)


def test_tool_request_invalid_timeout():
    """Verify that execution timeout overrides respect safety bounds."""
    with pytest.raises(ValidationError) as excinfo:
        ToolRequest(
            tool_name="system_shell",
            timeout_override=5000  # Above the 3600 limit
        )
    
    assert "Input should be less than or equal to 3600" in str(excinfo.value)


def test_execution_result_valid():
    """Verify that the execution telemetry model serializes correctly."""
    result = ExecutionResult(
        success=True,
        output="Hello World\n",
        runtime_ms=45.2
    )
    
    assert result.success is True
    assert result.output == "Hello World\n"
    assert result.error is None
    assert result.runtime_ms == 45.2


def test_execution_result_requires_runtime():
    """Verify that telemetry mandates execution time tracking."""
    with pytest.raises(ValidationError):
        ExecutionResult(
            success=False,
            output="",
            error="Process crashed"
        )  # Missing runtime_ms 