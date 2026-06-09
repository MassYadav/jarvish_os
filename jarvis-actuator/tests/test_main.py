import pytest
from fastapi.testclient import TestClient
from src.main import app
from src.core.config import get_settings

@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch, tmp_path):
    """
    Ensure the app's lifespan configuration check passes by injecting 
    required environment variables and isolating the workspace.
    """
    get_settings.cache_clear()
    monkeypatch.setenv("ACTUATOR_SHARED_SECRET", "super_secret_key_for_testing_purposes_only_32_chars")
    monkeypatch.setenv("WORKSPACE_DIR", str(tmp_path))


def test_health_check_endpoint():
    """Verify the diagnostic endpoint returns standard operational status."""
    # Using TestClient inside a context manager guarantees the app lifespan executes perfectly.
    with TestClient(app) as client:
        response = client.get("/health")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}. Content: {response.text}"
        
        data = response.json()
        assert data["status"] == "online"
        assert data["version"] == "0.1.0"
        assert data["workspace_active"] is True


def test_cors_preflight_rejection():
    """Verify that unauthorized external domains are blocked by CORS policies."""
    headers = {
        "Origin": "http://malicious-website.com",
        "Access-Control-Request-Method": "POST"
    }
    
    with TestClient(app) as client:
        response = client.options("/api/v1/execute", headers=headers)
        
        # If CORS blocks it, it will not return the allow-origin header for this domain
        assert response.status_code == 400 or "access-control-allow-origin" not in response.headers