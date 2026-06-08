from __future__ import annotations

from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def isolated_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from src.security.config import settings
    from src.security.emergency_stop import emergency_stop_manager

    audit_dir = tmp_path / "audit"
    screenshot_dir = tmp_path / "screenshots"

    monkeypatch.setattr(settings, "audit_dir", audit_dir)
    monkeypatch.setattr(settings, "audit_file_name", "actuator-audit.jsonl")
    monkeypatch.setattr(settings, "emergency_stop_file", audit_dir / "emergency-stop.lock")
    monkeypatch.setattr(settings, "lock_state_file", audit_dir / "actuator.lock")
    monkeypatch.setattr(settings, "screenshot_dir", screenshot_dir)
    monkeypatch.setattr(settings, "screenshot_metadata_file", "metadata.jsonl")
    monkeypatch.setattr(settings, "screenshot_retention_days", 7)
    monkeypatch.setattr(settings, "screenshot_max_files", 50)

    emergency_stop_manager.emergency_stop_file = settings.emergency_stop_file
    emergency_stop_manager.lock_state_file = settings.lock_state_file

    audit_dir.mkdir(parents=True, exist_ok=True)
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    yield tmp_path

    for marker in (settings.emergency_stop_file, settings.lock_state_file):
        marker.unlink(missing_ok=True)
