from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "JARVIS OS Gateway"
    DATABASE_URL: str
    
    # Phase 5 Addition: Redis Queue
    REDIS_URL: str = "redis://localhost:6379/0" 
    
    # Phase 1 Restored: Security & Auth Keys
    ENVIRONMENT: str = "development"
    SECRET_KEY: str
    VAULT_MASTER_KEY: str

    class Config:
        env_file = ".env"
        # This tells Pydantic not to crash if you add new things to .env later
        extra = "ignore" 

settings = Settings()