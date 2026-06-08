from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Any
import base64

from PIL import Image

from src.models.schemas import (
    Region,
    ScreenshotCaptureRequest,
    ScreenshotMetadata,
    ScreenshotMode,
)
from src.security.config import settings
from src.services.screenshot_store import screenshot_store
from src.services.window_service import WindowServiceError, window_service


class ScreenshotServiceError(RuntimeError):
    """Raised when screenshot capture cannot be completed."""


@dataclass(frozen=True)
class ScreenshotCapture:
    metadata: ScreenshotMetadata
    image_base64: str


class ScreenshotService:
    def capture(self, request: ScreenshotCaptureRequest) -> ScreenshotCapture:
        image, region, active_window_title = self._capture_image(request)
        labels = {
            "source": request.context.source,
            "requested_by": request.context.requested_by,
        }

        if request.persist and settings.screenshot_persistence_enabled:
            metadata = screenshot_store.save(
                image=image,
                execution_id=request.context.execution_id,
                mode=request.mode,
                active_window_title=active_window_title,
                region=region,
                labels=labels,
            )
        else:
            metadata = screenshot_store.build_transient_metadata(
                image=image,
                execution_id=request.context.execution_id,
                mode=request.mode,
                active_window_title=active_window_title,
                region=region,
                labels=labels,
            )

        return ScreenshotCapture(
            metadata=metadata,
            image_base64=self._encode_png_base64(image),
        )

    def _capture_image(
        self,
        request: ScreenshotCaptureRequest,
    ) -> tuple[Image.Image, Region | None, str | None]:
        if request.mode == ScreenshotMode.FULL:
            return self._capture_full(), None, window_service.get_active_window_title()

        if request.mode == ScreenshotMode.ACTIVE_WINDOW:
            return self._capture_active_window()

        if request.mode == ScreenshotMode.REGION:
            if request.region is None:
                raise ScreenshotServiceError("Region screenshot requires a region payload")
            return self._capture_region(request.region), request.region, window_service.get_active_window_title()

        raise ScreenshotServiceError(f"Unsupported screenshot mode: {request.mode}")

    def _capture_full(self) -> Image.Image:
        pyautogui = self._load_pyautogui()
        try:
            return pyautogui.screenshot()
        except Exception as exc:
            raise ScreenshotServiceError(f"Unable to capture full screenshot: {exc}") from exc

    def _capture_active_window(self) -> tuple[Image.Image, Region, str | None]:
        try:
            bounds = window_service.get_active_window_bounds()
        except WindowServiceError as exc:
            raise ScreenshotServiceError(str(exc)) from exc

        image = self._capture_region(bounds.region)
        return image, bounds.region, bounds.title

    def _capture_region(self, region: Region) -> Image.Image:
        pyautogui = self._load_pyautogui()
        try:
            return pyautogui.screenshot(
                region=(region.x, region.y, region.width, region.height)
            )
        except Exception as exc:
            raise ScreenshotServiceError(f"Unable to capture region screenshot: {exc}") from exc

    def _encode_png_base64(self, image: Image.Image) -> str:
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("ascii")

    def _load_pyautogui(self) -> Any:
        try:
            import pyautogui
        except ImportError as exc:
            raise ScreenshotServiceError("pyautogui is required for screenshots") from exc

        pyautogui.FAILSAFE = settings.pyautogui_failsafe
        return pyautogui


screenshot_service = ScreenshotService()
