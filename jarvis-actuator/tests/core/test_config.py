import pytest
from pydantic import ValidationError
from src.core.config import Settings, get_settings

@pytest.fixture(autouse=True)
def clear_settings_cache():
    """Ensure the settings cache is cleared before each test to prevent cross-contamination."""
    get_settings.cache_clear()

def test_settings_successful_initialization(monkeypatch, tmp_path):
    """Test that settings initialize correctly with valid environment variables."""
    test_secret = "a" * 32
    test_workspace = tmp_path / "jarvis_test_workspace"
    
    monkeypatch.setenv("ACTUATOR_SHARED_SECRET", test_secret)
    monkeypatch.setenv("WORKSPACE_DIR", str(test_workspace))
    monkeypatch.setenv("EXECUTION_TIMEOUT_SECONDS", "60")
    
    settings = get_settings()
    
    assert settings.ACTUATOR_SHARED_SECRET == test_secret
    assert settings.WORKSPACE_DIR == test_workspace.resolve()
    assert settings.EXECUTION_TIMEOUT_SECONDS == 60
    assert test_workspace.exists()

def test_settings_fails_missing_secret(monkeypatch):
    """Test that startup fails if the shared secret is missing."""
    monkeypatch.delenv("ACTUATOR_SHARED_SECRET", raising=False)
    
    with pytest.raises(ValidationError) as excinfo:
        get_settings()
    
    assert "Field required" in str(excinfo.value) or "missing" in str(excinfo.value).lower()

def test_settings_fails_weak_secret(monkeypatch):
    """Test that startup fails if the shared secret is too short."""
    monkeypatch.setenv("ACTUATOR_SHARED_SECRET", "short_secret")
    
    with pytest.raises(ValidationError) as excinfo:
        get_settings()
    
    assert "must be at least 32 characters long" in str(excinfo.value)

def test_settings_fails_invalid_timeout(monkeypatch):
    """Test that startup fails if timeout is out of bounds."""
    monkeypatch.setenv("ACTUATOR_SHARED_SECRET", "a" * 32)
    monkeypatch.setenv("EXECUTION_TIMEOUT_SECONDS", "-10")
    
    with pytest.raises(ValidationError) as excinfo:
        get_settings()
    
    assert "must be between 1 and 3600 seconds" in str(excinfo.value)