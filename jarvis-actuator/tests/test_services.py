from __future__ import annotations

from types import SimpleNamespace
import sys

import pytest

from src.models.schemas import MouseButton
from src.services.keyboard_service import KeyboardService
from src.services.mouse_service import MouseService
from src.services.process_service import ProcessService, ProcessServiceError


class FakePyAutoGUI:
    FAILSAFE = False

    def __init__(self) -> None:
        self.position_value = (0, 0)
        self.move_calls = []
        self.click_calls = []
        self.write_calls = []
        self.hotkey_calls = []

    def moveTo(self, *, x: int, y: int, duration: float) -> None:
        self.position_value = (x, y)
        self.move_calls.append({"x": x, "y": y, "duration": duration})

    def click(self, **kwargs) -> None:
        if "x" in kwargs and "y" in kwargs:
            self.position_value = (kwargs["x"], kwargs["y"])
        self.click_calls.append(kwargs)

    def position(self) -> tuple[int, int]:
        return self.position_value

    def write(self, text: str, *, interval: float) -> None:
        self.write_calls.append({"text": text, "interval": interval})

    def hotkey(self, *keys: str) -> None:
        self.hotkey_calls.append(keys)


def test_mouse_move_uses_pyautogui(monkeypatch):
    fake_pyautogui = FakePyAutoGUI()
    monkeypatch.setitem(sys.modules, "pyautogui", fake_pyautogui)

    result = MouseService().move(x=100, y=200, duration_seconds=0.25)

    assert result == {"x": 100, "y": 200}
    assert fake_pyautogui.move_calls == [{"x": 100, "y": 200, "duration": 0.25}]


def test_mouse_click_uses_requested_button(monkeypatch):
    fake_pyautogui = FakePyAutoGUI()
    monkeypatch.setitem(sys.modules, "pyautogui", fake_pyautogui)

    result = MouseService().click(
        x=10,
        y=20,
        button=MouseButton.RIGHT,
        clicks=2,
        interval_seconds=0.1,
    )

    assert result == {"x": 10, "y": 20, "button": "right", "clicks": 2}
    assert fake_pyautogui.click_calls == [
        {"x": 10, "y": 20, "button": "right", "clicks": 2, "interval": 0.1}
    ]


def test_keyboard_type_and_hotkey_use_pyautogui(monkeypatch):
    fake_pyautogui = FakePyAutoGUI()
    monkeypatch.setitem(sys.modules, "pyautogui", fake_pyautogui)
    service = KeyboardService()

    typed = service.type_text(text="hello", interval_seconds=0.05)
    hotkey = service.press_hotkey(keys=["ctrl", "s"])

    assert typed == {"characters_typed": 5}
    assert hotkey == {"keys": ["ctrl", "s"]}
    assert fake_pyautogui.write_calls == [{"text": "hello", "interval": 0.05}]
    assert fake_pyautogui.hotkey_calls == [("ctrl", "s")]


def test_keyboard_clipboard_uses_pyperclip(monkeypatch):
    clipboard = {"text": ""}

    fake_pyperclip = SimpleNamespace(
        copy=lambda value: clipboard.update({"text": value}),
        paste=lambda: clipboard["text"],
    )
    monkeypatch.setitem(sys.modules, "pyperclip", fake_pyperclip)
    service = KeyboardService()

    written = service.write_clipboard(text="copied")
    read = service.read_clipboard()

    assert written == {"characters_copied": 6}
    assert read == {"text": "copied"}


def test_process_launch_uses_shell_false(monkeypatch, tmp_path):
    calls = []

    class FakeProcess:
        pid = 1234

    def fake_popen(command, **kwargs):
        calls.append({"command": command, **kwargs})
        return FakeProcess()

    monkeypatch.setattr("src.services.process_service.subprocess.Popen", fake_popen)

    result = ProcessService().launch(
        application="notepad.exe",
        args=["file.txt"],
        working_directory=str(tmp_path),
    )

    assert result["pid"] == 1234
    assert result["application"] == "notepad.exe"
    assert calls[0]["command"] == ["notepad.exe", "file.txt"]
    assert calls[0]["shell"] is False
    assert calls[0]["cwd"] == str(tmp_path)


def test_process_rejects_null_byte_arguments():
    service = ProcessService()

    with pytest.raises(ProcessServiceError):
        service._build_command(application="notepad.exe", args=["bad\x00arg"])
