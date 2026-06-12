import uuid
import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Index, LargeBinary
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=False)
    preferences = Column(JSONB, server_default='{}')
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)
    
    # Establish cascade deletion to wipe the vault if the user is deleted
    credentials = relationship("VaultCredential", back_populates="user", cascade="all, delete-orphan")

class VaultCredential(Base):
    """
    Stores cryptographically isolated API keys per provider.
    service_name expects values like: 'groq', 'gemini', 'openrouter', etc.
    """
    __tablename__ = "vault_credentials"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    
    # The provider name (e.g., 'groq', 'gemini')
    service_name = Column(String, nullable=False)
    
    # Raw AES-256-GCM binary outputs
    ciphertext = Column(LargeBinary, nullable=False)
    nonce = Column(LargeBinary, nullable=False)
    
    updated_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    user = relationship("User", back_populates="credentials")

# Ensure a user can only have one active key per provider service
Index('ix_vault_user_service', VaultCredential.user_id, VaultCredential.service_name, unique=True)