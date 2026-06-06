import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# Force Python to load the .env file explicitly
load_dotenv()

# Parse the vault key outside the class to satisfy Pydantic v2 strict typing
_raw_vault_key = os.getenv("VAULT_MASTER_KEY", "0123456789abcdef0123456789abcdef")

class Settings(BaseSettings):
    PROJECT_NAME: str = "JARVIS API Gateway"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    
    # Fallback port is 5433
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://jarvis:jarvis_password@localhost:5433/jarvis_os")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-super-secret-jwt-key-jarvis")
    
    # Inject the strictly typed bytes object
    VAULT_MASTER_KEY: bytes = _raw_vault_key.encode('utf-8')[:32]
    
settings = Settings()