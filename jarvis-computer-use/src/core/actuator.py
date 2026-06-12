import os
import httpx
from typing import Dict, Any

class ActuatorClient:
    """Client to interface with the JARVIS Actuator Daemon."""
    
    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url
        self.client = httpx.Client(timeout=15.0)

    def get_screenshot(self) -> Dict[str, Any]:
        resp = self.client.post(f"{self.base_url}/actuator/desktop/screenshot", json={"return_base64": True})
        return resp.json()

    def get_active_window(self) -> Dict[str, Any]:
        resp = self.client.get(f"{self.base_url}/actuator/desktop/active_window")
        return resp.json()

    def get_clipboard(self) -> Dict[str, Any]:
        resp = self.client.get(f"{self.base_url}/actuator/desktop/clipboard")
        return resp.json()

    def click(self, x: int, y: int) -> Dict[str, Any]:
        resp = self.client.post(f"{self.base_url}/actuator/mouse/click", json={"x": x, "y": y})
        return resp.json()

    def type_text(self, text: str) -> Dict[str, Any]:
        resp = self.client.post(f"{self.base_url}/actuator/keyboard/type", json={"text": text})
        return resp.json()

    def hotkey(self, keys: list[str]) -> Dict[str, Any]:
        resp = self.client.post(f"{self.base_url}/actuator/keyboard/hotkey", json={"keys": keys})
        return resp.json()

    def open_target(self, target: str) -> Dict[str, Any]:
        resp = self.client.post(f"{self.base_url}/actuator/os/open", json={"target": target})
        return resp.json()
