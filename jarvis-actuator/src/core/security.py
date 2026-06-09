import hmac
import hashlib
import shlex
from typing import List, Union
from src.core.config import get_settings


def verify_signature(payload: bytes, signature: str) -> bool:
    """
    Verifies that the incoming request payload matches the provided HMAC SHA-256 signature.
    Employs constant-time comparison to prevent side-channel timing attacks.
    """
    if not signature:
        return False
        
    settings = get_settings()
    secret_bytes = settings.ACTUATOR_SHARED_SECRET.encode("utf-8")
    
    # Compute expected signature
    computed_hmac = hmac.new(secret_bytes, payload, hashlib.sha256)
    expected_signature = computed_hmac.hexdigest()
    
    return hmac.compare_digest(expected_signature, signature)


def is_command_safe(command: Union[str, List[str]]) -> bool:
    """
    Inspects system commands for shell injection vectors and dangerous evaluation syntax.
    Enforces that commands do not utilize chaining operators or dangerous substitutions.
    """
    # Prohibited shell mechanics. 
    # Note: Standalone ")" has been removed to allow valid strings like "print()" or paths like "(x86)".
    # We rely on "$(" and "`" to catch command substitution.
    forbidden_tokens = {";", "&&", "||", "|", "`", "$(", ">", "<", "\n", "\r"}
    
    if isinstance(command, list):
        # Inspect each pre-tokenized element for injection characters
        for token in command:
            if any(forbidden in token for forbidden in forbidden_tokens):
                return False
        return True

    if isinstance(command, str):
        # Strip simple whitespace and check for explicit shell operators
        cleaned_command = command.strip()
        if not cleaned_command:
            return False
            
        if any(forbidden in cleaned_command for forbidden in forbidden_tokens):
            return False
            
        try:
            # Parse via shell lexer to check if the string expands into unexpected command blocks
            lexed_tokens = shlex.split(cleaned_command)
            # Re-verify individual components extracted by the lexer
            for token in lexed_tokens:
                if any(forbidden in token for forbidden in forbidden_tokens):
                    return False
        except ValueError:
            # If shlex fails to parse due to mismatched quotes, flag as unsafe
            return False

        return True

    return False