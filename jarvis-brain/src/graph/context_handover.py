"""
jarvis-brain/src/graph/context_handover.py

Stateful Context Handover Manager for Dual-Core Orchestrator.

When the Deterministic Fast-Path (Playwright) fails on a task,
this module extracts the current browser session state and packages
it into a typed HandoverPayload. The VLM Computer Use Daemon receives
this context so it can orient itself at the exact failure point instead
of restarting the entire workflow from the homepage.

Extracted context:
  - current_url: The page Playwright was viewing when the failure occurred
  - cookies: All session cookies from the persistent browser context
  - local_storage: Key-value pairs from the page's localStorage
  - scroll_position: Current viewport scroll offset {x, y}
  - last_dom_snapshot: Truncated inner HTML around the failed element area
"""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from src.core.logger import logger


# ---------------------------------------------------------------------------
# Handover Payload Schema (type-safe, serializable)
# ---------------------------------------------------------------------------

class BrowserCookie(BaseModel):
    """Single cookie extracted from a Playwright browser context."""
    name: str
    value: str
    domain: str
    path: str = "/"
    secure: bool = False
    http_only: bool = False


class HandoverPayload(BaseModel):
    """
    Complete browser session state snapshot for VLM daemon orientation.

    This is injected into the VisionEscalationPayload.handover_context
    field so the daemon can skip all navigation steps the Fast-Path
    already completed.
    """
    current_url: str = ""
    cookies: List[BrowserCookie] = Field(default_factory=list)
    local_storage: Dict[str, str] = Field(default_factory=dict)
    scroll_position: Dict[str, int] = Field(default_factory=lambda: {"x": 0, "y": 0})
    last_dom_snapshot: str = Field(
        default="",
        description="Truncated inner HTML from the area of failure (max 5000 chars)",
    )


# ---------------------------------------------------------------------------
# DOM Snapshot Ceiling — prevents context window overflow
# ---------------------------------------------------------------------------

_DOM_SNAPSHOT_MAX_CHARS = 5_000


# ---------------------------------------------------------------------------
# Context Handover Manager
# ---------------------------------------------------------------------------

class ContextHandoverManager:
    """
    Extracts browser session state from the Playwright singleton agent.

    The extraction is wrapped in a try/finally so that even if the browser
    is in a corrupted state (which is why we're escalating), we still
    capture whatever we can and never leak the exception upward.
    """

    def extract_handover(self) -> HandoverPayload:
        """
        Pull the current session from the PlaywrightBrowserAgent singleton.

        Returns a fully populated HandoverPayload, or a minimal one if
        the browser is unreachable.
        """
        payload = HandoverPayload()

        try:
            from src.agents.browser.playwright_nav import _get_agent

            agent = _get_agent()

            # Guard: only extract if the agent has actually been started
            if not agent._started or agent._page is None:
                logger.info("handover_skipped_browser_not_started")
                return payload

            # All extraction runs on the Playwright background loop
            import asyncio

            future = asyncio.run_coroutine_threadsafe(
                self._async_extract(agent),
                agent._loop,
            )
            # 5-second budget — if the browser is truly stuck, don't hang
            payload = future.result(timeout=5)

        except Exception as e:
            logger.warning(
                "handover_extraction_partial_failure",
                error=str(e)[:200],
            )

        return payload

    async def _async_extract(self, agent) -> HandoverPayload:
        """
        Async extraction running inside the Playwright event loop.

        Each section is independently try/excepted so that a failure
        in cookie extraction doesn't block URL or DOM capture.
        """
        page = agent._page
        context = agent._context
        payload = HandoverPayload()

        # --- Current URL ---
        try:
            payload.current_url = page.url or ""
        except Exception:
            pass

        # --- Cookies ---
        try:
            raw_cookies = await context.cookies()
            payload.cookies = [
                BrowserCookie(
                    name=c.get("name", ""),
                    value=c.get("value", ""),
                    domain=c.get("domain", ""),
                    path=c.get("path", "/"),
                    secure=c.get("secure", False),
                    http_only=c.get("httpOnly", False),
                )
                for c in raw_cookies
            ]
        except Exception as e:
            logger.warning("handover_cookie_extraction_failed", error=str(e)[:100])

        # --- Local Storage ---
        try:
            ls_data = await page.evaluate("""
                () => {
                    const items = {};
                    for (let i = 0; i < localStorage.length; i++) {
                        const key = localStorage.key(i);
                        items[key] = localStorage.getItem(key);
                    }
                    return items;
                }
            """)
            payload.local_storage = ls_data if isinstance(ls_data, dict) else {}
        except Exception as e:
            logger.warning("handover_localstorage_extraction_failed", error=str(e)[:100])

        # --- Scroll Position ---
        try:
            scroll = await page.evaluate(
                "() => ({ x: window.scrollX, y: window.scrollY })"
            )
            payload.scroll_position = scroll if isinstance(scroll, dict) else {"x": 0, "y": 0}
        except Exception:
            pass

        # --- DOM Snapshot (truncated) ---
        try:
            html = await page.evaluate("() => document.body?.innerHTML || ''")
            payload.last_dom_snapshot = html[:_DOM_SNAPSHOT_MAX_CHARS] if html else ""
        except Exception:
            pass

        logger.info(
            "handover_extraction_complete",
            url=payload.current_url,
            cookies_count=len(payload.cookies),
            ls_keys=len(payload.local_storage),
        )

        return payload


# Module-level singleton
handover_manager = ContextHandoverManager()
