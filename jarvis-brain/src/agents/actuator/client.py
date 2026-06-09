import os
import httpx
import logging

logger = logging.getLogger(__name__)

class ActuatorClient:
    def __init__(self):
        # Actuator runs on port 8090 according to our architecture audit
        self.base_url = os.getenv("ACTUATOR_URL", "http://localhost:8090/actuator")

    def _post(self, endpoint: str, payload: dict = None):
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(f"{self.base_url}{endpoint}", json=payload or {})
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Actuator execution failed at {endpoint}: {e}")
            return {"error": str(e), "success": False}

    def screenshot_desktop(self):
        # FIXED: Now matches the Actuator POST endpoint we created earlier
        return self._post("/desktop/screenshot")

    def click_at(self, x: int, y: int):
        return self._post("/mouse/click", {"x": x, "y": y})

    def type_text(self, text: str):
        return self._post("/keyboard/type", {"text": text})

    def press_hotkey(self, keys: list[str]):
        return self._post("/keyboard/hotkey", {"keys": keys})

    def focus_window(self, title: str):
        return self._post("/window/focus", {"title": title})

    # NEW IRON MAN FEATURE: Open native applications or URLs
    def open_application(self, target: str):
        return self._post("/os/open", {"target": target})