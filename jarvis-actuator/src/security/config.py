from functools import lru_cache
from pathlib import Path
import platform

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _split_csv(value: str | list[str]) -> list[str]:
    if isinstance(value, list):
        return [item.strip() for item in value if item.strip()]
    return [item.strip() for item in value.split(",") if item.strip()]


class ActuatorSettings(BaseSettings):
    service_name: str = "jarvis-actuator"
    environment: str = "development"
    host: str = "127.0.0.1"
    port: int = Field(default=8090, ge=1, le=65535)

    platform_name: str = Field(default_factory=lambda: platform.system())
    windows_first: bool = True
    pyautogui_failsafe: bool = True
    default_action_timeout_seconds: float = Field(default=10.0, gt=0.0, le=60.0)

    allowed_applications: list[str] = Field(
        default_factory=lambda: [
            "notepad.exe",
            "calc.exe",
            "mspaint.exe",
            "explorer.exe",
            "code.exe",
            "chrome.exe",
            "msedge.exe",
        ]
    )
    denied_applications: list[str] = Field(
        default_factory=lambda: [
            "cmd.exe",
            "powershell.exe",
            "pwsh.exe",
            "regedit.exe",
            "taskmgr.exe",
            "mmc.exe",
            "services.msc",
            "secpol.msc",
            "gpedit.msc",
        ]
    )
    sensitive_window_terms: list[str] = Field(
        default_factory=lambda: [
            "password",
            "credential",
            "secret",
            "private key",
            "wallet",
            "bank",
            "security settings",
        ]
    )

    audit_dir: Path = Path("audit")
    audit_file_name: str = "actuator-audit.jsonl"
    emergency_stop_file: Path = Path("audit/emergency-stop.lock")
    lock_state_file: Path = Path("audit/actuator.lock")
    start_locked: bool = False

    screenshot_dir: Path = Path("screenshots")
    screenshot_persistence_enabled: bool = True
    screenshot_retention_days: int = Field(default=7, ge=1, le=365)
    screenshot_max_files: int = Field(default=500, ge=1, le=50_000)
    screenshot_metadata_file: str = "metadata.jsonl"

    approval_risk_threshold: int = Field(default=70, ge=0, le=100)
    force_approval_for_typing: bool = False
    force_approval_for_process_launch: bool = True
    force_approval_for_clipboard: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="ACTUATOR_",
        extra="ignore",
    )

    @field_validator(
        "allowed_applications",
        "denied_applications",
        "sensitive_window_terms",
        mode="before",
    )
    @classmethod
    def parse_csv_lists(cls, value: str | list[str]) -> list[str]:
        return _split_csv(value)

    @field_validator("allowed_applications", "denied_applications")
    @classmethod
    def normalize_application_names(cls, values: list[str]) -> list[str]:
        return sorted({value.strip().lower() for value in values if value.strip()})

    @field_validator("sensitive_window_terms")
    @classmethod
    def normalize_sensitive_terms(cls, values: list[str]) -> list[str]:
        return sorted({value.strip().lower() for value in values if value.strip()})


@lru_cache
def get_settings() -> ActuatorSettings:
    return ActuatorSettings()


settings = get_settings()
