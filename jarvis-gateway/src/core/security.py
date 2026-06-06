import os
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

# --- AES-256-GCM Vault ---
class Vault:
    def __init__(self):
        if settings.ENVIRONMENT == "production" and settings.VAULT_MASTER_KEY == b"0123456789abcdef0123456789abcdef":
            raise ValueError("CRITICAL: Default Vault Master Key detected in production.")
        self.aesgcm = AESGCM(settings.VAULT_MASTER_KEY)

    def _encrypt_sync(self, plaintext: str, user_id: str, service_name: str) -> tuple[bytes, bytes]:
        nonce = os.urandom(12)
        aad = f"{user_id}:{service_name}".encode('utf-8')  # Cryptographic binding
        ciphertext = self.aesgcm.encrypt(nonce, plaintext.encode('utf-8'), aad)
        return ciphertext, nonce

    def _decrypt_sync(self, ciphertext: bytes, nonce: bytes, user_id: str, service_name: str) -> str:
        aad = f"{user_id}:{service_name}".encode('utf-8')
        try:
            plaintext = self.aesgcm.decrypt(nonce, ciphertext, aad)
            return plaintext.decode('utf-8')
        except InvalidTag:
            logger.error("vault_decryption_failed", user_id=user_id, service_name=service_name)
            raise ValueError("Decryption failed. Data corrupted or AAD mismatch.")

    # Thread pooling prevents ASGI event loop blocking
    async def encrypt(self, plaintext: str, user_id: str, service_name: str) -> tuple[bytes, bytes]:
        return await asyncio.to_thread(self._encrypt_sync, plaintext, user_id, service_name)

    async def decrypt(self, ciphertext: bytes, nonce: bytes, user_id: str, service_name: str) -> str:
        return await asyncio.to_thread(self._decrypt_sync, ciphertext, nonce, user_id, service_name)

vault = Vault()