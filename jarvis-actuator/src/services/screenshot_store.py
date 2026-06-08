from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock
from uuid import uuid4
import json

from PIL import Image

from src.models.schemas import Region, ScreenshotMetadata, ScreenshotMode
from src.security.config import settings


_store_lock = Lock()


class ScreenshotStoreError(RuntimeError):
    """Raised when screenshot persistence cannot be completed."""


class ScreenshotStore:
    def __init__(self, screenshot_dir: Path | None = None) -> None:
        self.screenshot_dir = screenshot_dir or settings.screenshot_dir

    @property
    def metadata_path(self) -> Path:
        return self.screenshot_dir / settings.screenshot_metadata_file

    def save(
        self,
        *,
        image: Image.Image,
        execution_id: str,
        mode: ScreenshotMode,
        active_window_title: str | None = None,
        region: Region | None = None,
        labels: dict[str, str] | None = None,
    ) -> ScreenshotMetadata:
        screenshot_id = str(uuid4())
        created_at = datetime.now(UTC)
        file_name = f"{created_at.strftime('%Y%m%dT%H%M%S%fZ')}_{screenshot_id}.png"
        path = self.screenshot_dir / file_name

        with _store_lock:
            self.screenshot_dir.mkdir(parents=True, exist_ok=True)
            image.save(path, format="PNG")

            metadata = ScreenshotMetadata(
                screenshot_id=screenshot_id,
                execution_id=execution_id,
                mode=mode,
                width=image.width,
                height=image.height,
                path=str(path),
                created_at=created_at.isoformat(),
                active_window_title=active_window_title,
                region=region,
                labels=labels or {},
            )
            self._append_metadata(metadata)
            self.cleanup()
            return metadata

    def build_transient_metadata(
        self,
        *,
        image: Image.Image,
        execution_id: str,
        mode: ScreenshotMode,
        active_window_title: str | None = None,
        region: Region | None = None,
        labels: dict[str, str] | None = None,
    ) -> ScreenshotMetadata:
        return ScreenshotMetadata(
            screenshot_id=str(uuid4()),
            execution_id=execution_id,
            mode=mode,
            width=image.width,
            height=image.height,
            path=None,
            created_at=datetime.now(UTC).isoformat(),
            active_window_title=active_window_title,
            region=region,
            labels=labels or {},
        )

    def cleanup(self) -> dict[str, int]:
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        cutoff = datetime.now(UTC) - timedelta(days=settings.screenshot_retention_days)
        png_files = sorted(
            self.screenshot_dir.glob("*.png"),
            key=lambda path: path.stat().st_mtime,
        )

        removed = 0
        for path in list(png_files):
            modified_at = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
            if modified_at < cutoff:
                path.unlink(missing_ok=True)
                removed += 1

        png_files = sorted(
            self.screenshot_dir.glob("*.png"),
            key=lambda path: path.stat().st_mtime,
        )
        overflow = max(0, len(png_files) - settings.screenshot_max_files)
        for path in png_files[:overflow]:
            path.unlink(missing_ok=True)
            removed += 1

        return {"removed": removed, "remaining": len(list(self.screenshot_dir.glob('*.png')))}

    def _append_metadata(self, metadata: ScreenshotMetadata) -> None:
        with self.metadata_path.open("a", encoding="utf-8") as metadata_file:
            metadata_file.write(metadata.model_dump_json())
            metadata_file.write("\n")


screenshot_store = ScreenshotStore()
