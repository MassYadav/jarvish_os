import uuid
import structlog
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from src.core.config import settings
from src.core.security import vault
from src.db.models import VaultCredential

logger = structlog.get_logger()
router = APIRouter()

# Setup isolated sync session to prevent asyncpg blocking issues
sync_db_url = settings.DATABASE_URL.replace("+asyncpg", "")
engine = create_engine(sync_db_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class KeyStoreRequest(BaseModel):
    user_id: str
    provider_name: str  # e.g., 'groq', 'gemini', 'openai'
    api_key: str

@router.post("/")
async def store_api_key(req: KeyStoreRequest, db: Session = Depends(get_db)):
    """
    Receives a plaintext API key from the UI, encrypts it via AES-256-GCM, 
    and upserts it into the secure PostgreSQL Vault.
    """
    try:
        # 1. Validate UUID structural integrity
        user_uuid = uuid.UUID(req.user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id format. Must be a valid UUID.")
        
    try:
        # 2. Cryptographic Encryption
        # We pass user_id and provider_name to structurally bind the ciphertext (AAD)
        ciphertext, nonce = vault._encrypt_sync(
            plaintext=req.api_key, 
            user_id=req.user_id, 
            service_name=req.provider_name
        )
        
        # 3. Vault Upsert Logic
        existing_cred = db.query(VaultCredential).filter_by(
            user_id=user_uuid, 
            service_name=req.provider_name
        ).first()
        
        if existing_cred:
            # Update existing credential
            existing_cred.ciphertext = ciphertext
            existing_cred.nonce = nonce
            logger.info("vault_credential_updated", user_id=req.user_id, provider=req.provider_name)
        else:
            # Insert brand new credential
            new_cred = VaultCredential(
                user_id=user_uuid,
                service_name=req.provider_name,
                ciphertext=ciphertext,
                nonce=nonce
            )
            db.add(new_cred)
            logger.info("vault_credential_created", user_id=req.user_id, provider=req.provider_name)
            
        db.commit()
        return {"status": "success", "message": f"Successfully secured {req.provider_name} API key."}
        
    except Exception as e:
        db.rollback()
        logger.error("vault_storage_failed", error=str(e), user_id=req.user_id)
        raise HTTPException(status_code=500, detail=f"Failed to secure API key: {str(e)}")