from __future__ import annotations

from typing import Any

from src.models.schemas import MouseButton
from src.security.config import settings


class MouseServiceError(RuntimeError):
    """Raised when mouse automation cannot be completed."""


class MouseService:
    def move(self, *, x: int, y: int, duration_seconds: float = 0.0) -> dict[str, int]:
        pyautogui = self._load_pyautogui()
        try:
            pyautogui.moveTo(x=x, y=y, duration=duration_seconds)
            current_x, current_y = pyautogui.position()
            return {"x": int(current_x), "y": int(current_y)}
        except Exception as exc:
            raise MouseServiceError(f"Unable to move mouse: {exc}") from exc

    def click(
        self,
        *,
        x: int | None = None,
        y: int | None = None,
        button: MouseButton = MouseButton.LEFT,
        clicks: int = 1,
        interval_seconds: float = 0.0,
    ) -> dict[str, int | str]:
        pyautogui = self._load_pyautogui()
        try:
            if x is not None and y is not None:
                pyautogui.click(
                    x=x,
                    y=y,
                    button=button.value,
                    clicks=clicks,
                    interval=interval_seconds,
                )
            else:
                pyautogui.click(
                    button=button.value,
                    clicks=clicks,
                    interval=interval_seconds,
                )

            current_x, current_y = pyautogui.position()
            return {
                "x": int(current_x),
                "y": int(current_y),
                "button": button.value,
                "clicks": clicks,
            }
        except Exception as exc:
            raise MouseServiceError(f"Unable to click mouse: {exc}") from exc

    def _load_pyautogui(self) -> Any:
        try:
            import pyautogui
        except ImportError as exc:
            raise MouseServiceError("pyautogui is required for mouse automation") from exc

        pyautogui.FAILSAFE = settings.pyautogui_failsafe
        return pyautogui


mouse_service = MouseService()
