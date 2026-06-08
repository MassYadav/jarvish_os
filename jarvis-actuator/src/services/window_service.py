from __future__ import annotations

from dataclasses import dataclass
from time import sleep
from typing import Any

from src.models.schemas import Region, WindowInfo


class WindowServiceError(RuntimeError):
    """Raised when the host window manager cannot complete the request."""


@dataclass(frozen=True)
class WindowBounds:
    title: str
    region: Region


class WindowService:
    def list_windows(self) -> list[WindowInfo]:
        windows = []
        for window in self._get_all_windows():
            title = str(getattr(window, "title", "") or "").strip()
            if not title:
                continue

            windows.append(
                WindowInfo(
                    title=title,
                    is_active=bool(getattr(window, "isActive", False)),
                    is_minimized=bool(getattr(window, "isMinimized", False)),
                    left=self._safe_int(getattr(window, "left", None)),
                    top=self._safe_int(getattr(window, "top", None)),
                    width=self._safe_int(getattr(window, "width", None)),
                    height=self._safe_int(getattr(window, "height", None)),
                    handle=self._safe_int(getattr(window, "_hWnd", None)),
                    process_name=None,
                )
            )
        return windows

    def focus_window(self, title: str, exact_match: bool = False) -> WindowInfo:
        window = self._find_window(title=title, exact_match=exact_match)

        if bool(getattr(window, "isMinimized", False)):
            window.restore()
            sleep(0.1)

        window.activate()
        sleep(0.1)

        return WindowInfo(
            title=str(getattr(window, "title", "") or ""),
            is_active=bool(getattr(window, "isActive", True)),
            is_minimized=bool(getattr(window, "isMinimized", False)),
            left=self._safe_int(getattr(window, "left", None)),
            top=self._safe_int(getattr(window, "top", None)),
            width=self._safe_int(getattr(window, "width", None)),
            height=self._safe_int(getattr(window, "height", None)),
            handle=self._safe_int(getattr(window, "_hWnd", None)),
            process_name=None,
        )

    def get_active_window_title(self) -> str | None:
        active_window = self._get_active_window()
        if active_window is None:
            return None
        title = str(getattr(active_window, "title", "") or "").strip()
        return title or None

    def get_active_window_bounds(self) -> WindowBounds:
        active_window = self._get_active_window()
        if active_window is None:
            raise WindowServiceError("No active window is available")

        title = str(getattr(active_window, "title", "") or "").strip()
        left = self._safe_int(getattr(active_window, "left", None))
        top = self._safe_int(getattr(active_window, "top", None))
        width = self._safe_int(getattr(active_window, "width", None))
        height = self._safe_int(getattr(active_window, "height", None))

        if left is None or top is None or width is None or height is None:
            raise WindowServiceError("Active window bounds are unavailable")

        if width <= 0 or height <= 0:
            raise WindowServiceError("Active window has invalid dimensions")

        return WindowBounds(
            title=title,
            region=Region(x=max(left, 0), y=max(top, 0), width=width, height=height),
        )

    def _find_window(self, *, title: str, exact_match: bool) -> Any:
        requested_title = title.strip()
        if not requested_title:
            raise WindowServiceError("Window title cannot be empty")

        matches = []
        for window in self._get_all_windows():
            window_title = str(getattr(window, "title", "") or "").strip()
            if not window_title:
                continue

            if exact_match and window_title == requested_title:
                matches.append(window)
            elif not exact_match and requested_title.lower() in window_title.lower():
                matches.append(window)

        if not matches:
            mode = "exact" if exact_match else "partial"
            raise WindowServiceError(f"No window found for {mode} title match: {requested_title}")

        return matches[0]

    def _get_all_windows(self) -> list[Any]:
        gateway = self._load_pygetwindow()
        try:
            return list(gateway.getAllWindows())
        except Exception as exc:
            raise WindowServiceError(f"Unable to list windows: {exc}") from exc

    def _get_active_window(self) -> Any | None:
        gateway = self._load_pygetwindow()
        try:
            return gateway.getActiveWindow()
        except Exception as exc:
            raise WindowServiceError(f"Unable to read active window: {exc}") from exc

    def _load_pygetwindow(self) -> Any:
        try:
            import pygetwindow
        except ImportError as exc:
            raise WindowServiceError(
                "pygetwindow is required for desktop window automation"
            ) from exc
        return pygetwindow

    def _safe_int(self, value: Any) -> int | None:
        try:
            if value is None:
                return None
            return int(value)
        except (TypeError, ValueError):
            return None


window_service = WindowService()
