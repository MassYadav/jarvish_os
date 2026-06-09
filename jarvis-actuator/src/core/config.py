import os
from functools import lru_cache
from pathlib import Path
from typing import Literal
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Core configuration for the JARVIS Actuator execution daemon.
    Enforces strict security boundaries and network bindings.
    """
    
    # Network Bindings
    ACTUATOR_HOST: str = Field(default="127.0.0.1", description="Bind address. Default to localhost for security.")
    ACTUATOR_PORT: int = Field(default=8001, description="Port for the REST/RPC API.")
    
    # Security Parameters
    ACTUATOR_SHARED_SECRET: str = Field(
        ..., 
        description="Cryptographic key for HMAC payload verification. Must be securely generated."
    )
    
    # Execution Constraints
    EXECUTION_TIMEOUT_SECONDS: int = Field(
        default=120, 
        description="Maximum allowed time for a system command or automation script to run."
    )
    
    # File System Isolation
    WORKSPACE_DIR: Path = Field(
        default=Path(os.path.expanduser("~/.jarvis_workspace")),
        description="Root directory for file-based operations. Commands outside this directory are prohibited."
    )
    
    # Observability
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Standard logging level."
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    @field_validator("ACTUATOR_SHARED_SECRET")
    @classmethod
    def validate_secret_strength(cls, value: str) -> str:
        """Ensure the shared secret is cryptographically robust."""
        if len(value) < 32:
            raise ValueError("ACTUATOR_SHARED_SECRET must be at least 32 characters long.")
        return value

    @field_validator("EXECUTION_TIMEOUT_SECONDS")
    @classmethod
    def validate_timeout(cls, value: int) -> int:
        """Prevent infinite execution horizons."""
        if value <= 0 or value > 3600:
            raise ValueError("EXECUTION_TIMEOUT_SECONDS must be between 1 and 3600 seconds.")
        return value

    @field_validator("WORKSPACE_DIR")
    @classmethod
    def setup_workspace(cls, value: Path) -> Path:
        """
        Ensure the workspace directory exists and is strictly an absolute path.
        Creates the directory if it does not exist to ensure runtime stability.
        """
        absolute_path = value.resolve()
        try:
            absolute_path.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            raise ValueError(f"Insufficient permissions to create WORKSPACE_DIR at {absolute_path}")
        return absolute_path


@lru_cache
def get_settings() -> Settings:
    """
    Lazy-loads and caches the settings singleton.
    Prevents premature validation errors during test collection or module imports.
    """
    return Settings()