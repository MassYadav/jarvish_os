from pathlib import Path
import os
import time

from PIL import Image

from src.models.schemas import ScreenshotMode
from src.security.config import settings
from src.services.screenshot_store import ScreenshotStore


def test_screenshot_store_persists_image_and_metadata(isolated_runtime):
    store = ScreenshotStore(settings.screenshot_dir)
    image = Image.new("RGB", (20, 10), color="blue")

    metadata = store.save(
        image=image,
        execution_id="exec-1",
        mode=ScreenshotMode.FULL,
        labels={"phase": "test"},
    )

    assert metadata.execution_id == "exec-1"
    assert metadata.width == 20
    assert metadata.height == 10
    assert metadata.path is not None
    assert Path(metadata.path).exists()
    assert store.metadata_path.exists()
    assert "exec-1" in store.metadata_path.read_text(encoding="utf-8")


def test_transient_metadata_does_not_persist_file(isolated_runtime):
    store = ScreenshotStore(settings.screenshot_dir)
    image = Image.new("RGB", (5, 5), color="green")

    metadata = store.build_transient_metadata(
        image=image,
        execution_id="exec-2",
        mode=ScreenshotMode.FULL,
    )

    assert metadata.path is None
    assert list(settings.screenshot_dir.glob("*.png")) == []


def test_cleanup_removes_overflow_files(isolated_runtime, monkeypatch):
    monkeypatch.setattr(settings, "screenshot_max_files", 1)
    store = ScreenshotStore(settings.screenshot_dir)

    old_file = settings.screenshot_dir / "old.png"
    new_file = settings.screenshot_dir / "new.png"
    Image.new("RGB", (1, 1), color="red").save(old_file)
    time.sleep(0.01)
    Image.new("RGB", (1, 1), color="blue").save(new_file)

    result = store.cleanup()

    remaining = list(settings.screenshot_dir.glob("*.png"))
    assert result["removed"] == 1
    assert len(remaining) == 1
    assert remaining[0].name == "new.png"


def test_cleanup_removes_expired_files(isolated_runtime, monkeypatch):
    monkeypatch.setattr(settings, "screenshot_retention_days", 1)
    store = ScreenshotStore(settings.screenshot_dir)

    expired_file = settings.screenshot_dir / "expired.png"
    Image.new("RGB", (1, 1), color="red").save(expired_file)
    old_timestamp = time.time() - (3 * 24 * 60 * 60)
    os.utime(expired_file, (old_timestamp, old_timestamp))

    result = store.cleanup()

    assert result["removed"] == 1
    assert expired_file.exists() is False
