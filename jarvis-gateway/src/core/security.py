import os
import base64
import asyncio
from datetime import datetime, timedelta
from jose import jwt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag
import structlog
from src.core.config import settings

logger = structlog.get_logger()

# --- JWT Auth ---
def create_access_token(data: dict, expires_delta: timedelta = timedelta(hours=24)):
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")

# --- AES-256-GCM Vault (Iron Man BYOAK Upgrade) ---
class Vault:
    def __init__(self):
        # Read the newly generated Base64 Master Key from the environment
        raw_key = os.getenv("JARVIS_MASTER_KEY")
        if not raw_key:
            # Fallback to older settings if environment variable isn't injected yet
            if hasattr(settings, 'VAULT_MASTER_KEY'):
                if settings.ENVIRONMENT == "production" and settings.VAULT_MASTER_KEY == "0123456789abcdef0123456789abcdef":
                    raise ValueError("CRITICAL: Default Vault Master Key detected in production.")
                self.key = settings.VAULT_MASTER_KEY.encode('utf-8')
            else:
                raise RuntimeError("CRITICAL: JARVIS_MASTER_KEY environment variable is missing.")
        else:
            self.key = base64.b64decode(raw_key)

        if len(self.key) != 32:
            raise ValueError("Master key must resolve to exactly 32 bytes.")
            
        self.aesgcm = AESGCM(self.key)

    def _encrypt_sync(self, plaintext: str, user_id: str, service_name: str) -> tuple[bytes, bytes]:
        if not plaintext:
            raise ValueError("Cannot encrypt an empty payload.")
        nonce = os.urandom(12)
        # Cryptographic binding: Locks the key to this specific user and provider
        aad = f"{user_id}:{service_name}".encode('utf-8')  
        ciphertext = self.aesgcm.encrypt(nonce, plaintext.encode('utf-8'), aad)
        return ciphertext, nonce

    def _decrypt_sync(self, ciphertext: bytes, nonce: bytes, user_id: str, service_name: str) -> str:
        aad = f"{user_id}:{service_name}".encode('utf-8')
        try:
            plaintext = self.aesgcm.decrypt(nonce, ciphertext, aad)
            return plaintext.decode('utf-8')
        except InvalidTag:
            logger.error("vault_decryption_failed", user_id=user_id, service_name=service_name)
            raise ValueError("Decryption failed. Data corrupted or AAD context mismatch.")

    # Thread pooling prevents ASGI event loop blocking
    async def encrypt(self, plaintext: str, user_id: str, service_name: str) -> tuple[bytes, bytes]:
        return await asyncio.to_thread(self._encrypt_sync, plaintext, user_id, service_name)

    async def decrypt(self, ciphertext: bytes, nonce: bytes, user_id: str, service_name: str) -> str:
        return await asyncio.to_thread(self._decrypt_sync, ciphertext, nonce, user_id, service_name)

vault = Vault()