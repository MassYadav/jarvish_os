import hmac
import hashlib
import json
import sys
import asyncio
import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from src.core.config import get_settings
from src.api.routes import router

# Setup a temporary FastAPI app to mount our router for testing
app = FastAPI()
app.include_router(router)

@pytest.fixture(autouse=True)
def setup_api_test_environment(monkeypatch):
    """Ensure a clean environment and consistent secret key for API tests."""
    get_settings.cache_clear()
    monkeypatch.setenv("ACTUATOR_SHARED_SECRET", "super_secret_key_for_testing_purposes_only_32_chars")


def generate_signature_for_bytes(payload_bytes: bytes) -> str:
    """Helper to generate a valid HMAC signature for exact byte payloads."""
    settings = get_settings()
    secret_bytes = settings.ACTUATOR_SHARED_SECRET.encode("utf-8")
    return hmac.new(secret_bytes, payload_bytes, hashlib.sha256).hexdigest()


@pytest.mark.anyio
async def test_execute_missing_signature():
    """Verify that omitting the HMAC header blocks the request entirely."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/execute", json={"tool_name": "system_shell", "parameters": {}})
        assert response.status_code == 401
        assert "Missing" in response.json()["detail"]


@pytest.mark.anyio
async def test_execute_invalid_signature():
    """Verify that a forged or incorrect HMAC header is rejected."""
    headers = {"X-Jarvis-Signature": "forged_bad_signature_123"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/execute", json={"tool_name": "system_shell", "parameters": {}}, headers=headers)
        assert response.status_code == 401
        assert "verification failed" in response.json()["detail"]


@pytest.mark.anyio
async def test_execute_and_check_status_success():
    """Verify the full lifecycle: Signed Request -> Task ID -> Completion."""
    payload = {
        "tool_name": "system_shell",
        "parameters": {
            "command": [sys.executable, "-c", "print('hello api')"]
        }
    }
    
    # Serialize to exact bytes FIRST to guarantee cryptographic matching
    payload_bytes = json.dumps(payload).encode("utf-8")
    signature = generate_signature_for_bytes(payload_bytes)
    
    headers = {
        "X-Jarvis-Signature": signature,
        "Content-Type": "application/json"
    }
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Dispatch the payload asynchronously
        response = await client.post("/api/v1/execute", content=payload_bytes, headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}. Response: {response.text}"
        
        data = response.json()
        assert "task_id" in data
        assert data["status"] == "pending"
        
        task_id = data["task_id"]
        
        # 2. Poll status (simulating async waiting via asyncio.sleep)
        max_retries = 20
        for _ in range(max_retries):
            status_response = await client.get(f"/api/v1/tasks/{task_id}/status")
            assert status_response.status_code == 200
            
            status_data = status_response.json()
            if status_data["status"] == "completed":
                error_msg = status_data["result"].get("error", "Unknown OS Error")
                assert status_data["result"]["success"] is True, f"Execution failed: {error_msg}"
                assert "hello api" in status_data["result"]["output"]
                break
                
            await asyncio.sleep(0.1)
        else:
            pytest.fail("Task did not complete in time.")


@pytest.mark.anyio
async def test_abort_task_requires_signature():
    """Verify that attackers cannot cancel running tasks without authentication."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/tasks/fake-uuid-123/abort")
        assert response.status_code == 401