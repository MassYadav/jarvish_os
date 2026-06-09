import pytest
import sys
from src.runtime.executor import execute_command
from src.core.config import get_settings

# Use the current Python executable to ensure cross-platform compatibility on Windows/Linux
PYTHON_EXEC = sys.executable

@pytest.fixture(autouse=True)
def setup_test_workspace(monkeypatch, tmp_path):
    """Ensure a clean workspace exists for tests."""
    get_settings.cache_clear()
    monkeypatch.setenv("ACTUATOR_SHARED_SECRET", "super_secret_key_for_testing_purposes_only_32_chars")
    monkeypatch.setenv("WORKSPACE_DIR", str(tmp_path))


@pytest.mark.anyio
async def test_execute_command_success():
    """Verify that a valid command executes successfully and captures stdout."""
    # We use python to print a string safely across OS platforms
    command = [PYTHON_EXEC, "-c", "print('hello jarvis')"]
    
    result = await execute_command(command)
    
    assert result.success is True
    assert "hello jarvis" in result.output
    assert result.error is None
    assert result.runtime_ms > 0


@pytest.mark.anyio
async def test_execute_command_execution_failure():
    """Verify that a command returning a non-zero exit code captures stderr."""
    # Force an intentional python syntax error
    command = [PYTHON_EXEC, "-c", "raise ValueError('System Failure')"]
    
    result = await execute_command(command)
    
    assert result.success is False
    assert result.error is not None
    assert "System Failure" in result.error
    assert result.runtime_ms > 0


@pytest.mark.anyio
async def test_execute_command_not_found():
    """Verify that attempting to run a non-existent binary is caught cleanly."""
    command = ["non_existent_binary_xyz_123"]
    
    result = await execute_command(command)
    
    assert result.success is False
    assert "Executable not found" in result.error
    assert "non_existent_binary_xyz_123" in result.error


@pytest.mark.anyio
async def test_execute_command_timeout():
    """Verify that long-running rogue commands are terminated and return a Timeout error."""
    # A python script that sleeps for 5 seconds
    command = [PYTHON_EXEC, "-c", "import time; time.sleep(5)"]
    
    # Override timeout to 1 second
    result = await execute_command(command, timeout_override=1)
    
    assert result.success is False
    assert "Execution timed out" in result.error
    assert result.runtime_ms < 2000  # Should definitely finish well before 2 seconds