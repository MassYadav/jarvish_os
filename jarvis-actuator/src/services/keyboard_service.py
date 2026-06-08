from __future__ import annotations

from typing import Any

from src.security.config import settings


class KeyboardServiceError(RuntimeError):
    """Raised when keyboard or clipboard automation cannot be completed."""


class KeyboardService:
    def type_text(self, *, text: str, interval_seconds: float = 0.0) -> dict[str, int]:
        pyautogui = self._load_pyautogui()
        try:
            pyautogui.write(text, interval=interval_seconds)
            return {"characters_typed": len(text)}
        except Exception as exc:
            raise KeyboardServiceError(f"Unable to type text: {exc}") from exc

    def press_hotkey(self, *, keys: list[str]) -> dict[str, list[str]]:
        if not keys:
            raise KeyboardServiceError("At least one hotkey is required")

        pyautogui = self._load_pyautogui()
        try:
            pyautogui.hotkey(*keys)
            return {"keys": keys}
        except Exception as exc:
            raise KeyboardServiceError(f"Unable to press hotkey: {exc}") from exc

    def read_clipboard(self) -> dict[str, str]:
        pyperclip = self._load_pyperclip()
        try:
            return {"text": str(pyperclip.paste())}
        except Exception as exc:
            raise KeyboardServiceError(f"Unable to read clipboard: {exc}") from exc

    def write_clipboard(self, *, text: str) -> dict[str, int]:
        pyperclip = self._load_pyperclip()
        try:
            pyperclip.copy(text)
            return {"characters_copied": len(text)}
        except Exception as exc:
            raise KeyboardServiceError(f"Unable to write clipboard: {exc}") from exc

    def _load_pyautogui(self) -> Any:
        try:
            import pyautogui
        except ImportError as exc:
            raise KeyboardServiceError("pyautogui is required for keyboard automation") from exc

        pyautogui.FAILSAFE = settings.pyautogui_failsafe
        return pyautogui

    def _load_pyperclip(self) -> Any:
        try:
            import pyperclip
        except ImportError as exc:
            raise KeyboardServiceError("pyperclip is required for clipboard automation") from exc
        return pyperclip


keyboard_service = KeyboardService()
