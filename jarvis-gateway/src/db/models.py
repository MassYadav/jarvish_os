import uuid
import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Index, LargeBinary
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=False)
    preferences = Column(JSONB, server_default='{}')
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)

class VaultCredential(Base):
    __tablename__ = "vault_credentials"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'))
    service_name = Column(String, nullable=False)
    ciphertext = Column(LargeBinary, nullable=False)
    nonce = Column(LargeBinary, nullable=False)

Index('ix_vault_user_service', VaultCredential.user_id, VaultCredential.service_name, unique=True)