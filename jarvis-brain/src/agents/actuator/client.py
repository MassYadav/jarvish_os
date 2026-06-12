# jarvis-brain/src/agents/actuator/client.py
import os
import httpx
import logging

logger = logging.getLogger(__name__)

class ActuatorClient:
    def __init__(self):
        # Actuator daemon routing configuration
        self.base_url = os.getenv("ACTUATOR_URL", "http://localhost:8001/actuator")
        
        # PRODUCTION UPGRADE: Maintain a persistent connection pool.
        # This keeps the TCP connection alive, reducing action latency to near 0ms.
        self.session = httpx.Client(
            timeout=15.0,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
        )

    def _post(self, endpoint: str, payload: dict = None) -> dict:
        url = f"{self.base_url}{endpoint}"
        try:
            # Reusing the persistent session instead of recreating it every time
            response = self.session.post(url, json=payload or {})
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Actuator HTTP Error at {endpoint} [Status {e.response.status_code}]: {e.response.text}")
            return {"status": "error", "message": f"HTTP execution fault: {str(e)}"}
        except Exception as e:
            logger.error(f"Actuator transport failure at {endpoint}: {e}")
            return {"status": "error", "message": f"Transport layer fault: {str(e)}"}

    def screenshot_desktop(self) -> dict:
        """Captures local desktop frame and updates workspace cache."""
        return self._post("/desktop/screenshot")

    def click_at(self, x: int, y: int) -> dict:
        """Triggers local hardware mouse click at specified coordinates."""
        return self._post("/mouse/click", {"x": x, "y": y})

    def type_text(self, text: str) -> dict:
        """Injects hardware-level keystroke sequences."""
        return self._post("/keyboard/type", {"text": text})

    def press_hotkey(self, keys: list[str]) -> dict:
        """Executes multi-key modifier combinations (e.g., ['ctrl', 'c'])."""
        return self._post("/keyboard/hotkey", {"keys": keys})

    def focus_window(self, title: str) -> dict:
        """Brings the specific target operating system window into focus context."""
        return self._post("/window/focus", {"title": title})

    def open_application(self, target: str) -> dict:
        """Executes native applications or fires default browser strings (URLs)."""
        return self._post("/os/open", {"target": target})

    def close(self):
        """Gracefully releases connection pools when the agent runtime shuts down."""
        self.session.close()