"""
jarvis-brain/src/agents/browser/playwright_nav.py

Production-grade web automation layer for JARVIS.

Architecture:
  PlaywrightBrowserAgent   — stateful class owning one persistent Chromium context.
                             Runs async Playwright inside a dedicated background
                             event loop so it can co-exist with the synchronous
                             Redis worker without blocking either side.

  Singleton _agent         — lazily initialised on first tool call; shutdown via
                             shutdown_browser_agent() called from tools.py teardown.

Public sync tool wrappers (TOOL_REGISTRY-compatible):
  browse_web(url)                     — existing scrape tool (kept for compat)
  browser_navigate(url)               — headful navigate + networkidle wait
  browser_click(selector)             — robust click with actionability wait
  browser_type(selector, text)        — focused field keystroke injection
  browser_scrape_text(selector?)      — inner-text extraction
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup
import markdownify
from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Page,
    TimeoutError as PlaywrightTimeoutError,
)
from playwright.sync_api import sync_playwright

from src.core.logger import logger


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Hard timeout for every Playwright wait call (spec §4 — 15 second max)
ACTION_TIMEOUT_MS: int = 15_000

# Session persistence directory — keeps cookies/logins across runs
_SESSION_DIR: Path = Path.home() / ".jarvis_browser_profile"


# ---------------------------------------------------------------------------
# Structured log emitter (spec §3)
# ---------------------------------------------------------------------------

def _emit(action: str, **kwargs) -> None:
    """
    Emit a structured JSON event to the structlog logger and directly to stdout.

    Every browser action produces a line of the form:
      {"event": "browser_action", "status": "success", "action": "...", ..., "timestamp": "..."}
    """
    payload = {
        "event": "browser_action",
        "status": "success",
        "action": action,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **kwargs,
    }
    # structlog
    logger.info("browser_action", **{k: v for k, v in payload.items() if k not in ("event", "status")})
    # Direct stdout JSON — satisfies spec §3 explicit stdout requirement
    print(json.dumps(payload), flush=True)


def _emit_error(action: str, error: str, **kwargs) -> None:
    payload = {
        "event": "browser_action",
        "status": "error",
        "action": action,
        "error": error,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **kwargs,
    }
    logger.error("browser_action", **{k: v for k, v in payload.items() if k not in ("event", "status")})
    print(json.dumps(payload), flush=True)


# ---------------------------------------------------------------------------
# PlaywrightBrowserAgent — stateful, headful, persistent context
# ---------------------------------------------------------------------------

class PlaywrightBrowserAgent:
    """
    Manages a single, persistent Chromium browser context in headful mode.

    The async Playwright API runs on a private background event loop
    (self._loop) owned by a dedicated daemon thread (self._thread).
    All public methods are synchronous — they submit coroutines to that loop
    via asyncio.run_coroutine_threadsafe() and block until done.

    Session persistence:
      user_data_dir=_SESSION_DIR keeps cookies, local storage, and
      IndexedDB intact across restarts, enabling persisted logins for
      Google, LinkedIn, GitHub, etc.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._started = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _run_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Background thread target: runs the event loop forever."""
        asyncio.set_event_loop(loop)
        loop.run_forever()

    def _ensure_started(self) -> None:
        """Lazily start the background event loop and launch the browser."""
        if self._started:
            return
        with self._lock:
            if self._started:
                return
            self._loop = asyncio.new_event_loop()
            self._thread = threading.Thread(
                target=self._run_loop,
                args=(self._loop,),
                daemon=True,
                name="playwright-event-loop",
            )
            self._thread.start()
            # Block until the browser is fully ready
            future = asyncio.run_coroutine_threadsafe(self._async_start(), self._loop)
            future.result(timeout=30)
            self._started = True
            logger.info("browser_agent_started", user_data_dir=str(_SESSION_DIR))

    def _submit(self, coro) -> object:
        """Submit a coroutine to the background loop and return its result synchronously."""
        self._ensure_started()
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=ACTION_TIMEOUT_MS / 1000 + 5)  # extra 5 s buffer

    async def _async_start(self) -> None:
        """Launch Chromium in headful mode with a persistent session directory."""
        _SESSION_DIR.mkdir(parents=True, exist_ok=True)

        self._playwright = await async_playwright().start()

        # launch_persistent_context = headful + cookie/session persistence in one call
        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(_SESSION_DIR),
            headless=False,                  # spec §1 — visible browser window
            args=[
                "--start-maximized",
                "--disable-blink-features=AutomationControlled",  # stealth
                "--no-first-run",
                "--no-default-browser-check",
            ],
            ignore_https_errors=True,
            viewport=None,                   # use OS window size when headful
        )

        # Reuse existing page if the context already has one (persisted session)
        if self._context.pages:
            self._page = self._context.pages[0]
        else:
            self._page = await self._context.new_page()

        # Set default timeouts (spec §4 — 10-second ceiling)
        self._page.set_default_timeout(ACTION_TIMEOUT_MS)
        self._page.set_default_navigation_timeout(ACTION_TIMEOUT_MS)

    async def _async_shutdown(self) -> None:
        if self._context:
            await self._context.close()
        if self._playwright:
            await self._playwright.stop()

    def shutdown(self) -> None:
        """Gracefully close the browser and stop the event loop. Call from teardown."""
        if not self._started:
            return
        future = asyncio.run_coroutine_threadsafe(self._async_shutdown(), self._loop)
        try:
            future.result(timeout=10)
        except Exception:
            pass
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._started = False
        logger.info("browser_agent_shutdown")

    # ------------------------------------------------------------------
    # Tool implementations (async, run inside the background loop)
    # ------------------------------------------------------------------

    async def _async_navigate(self, url: str) -> dict:
        try:
            response = await self._page.goto(
                url,
                wait_until="networkidle",
                timeout=ACTION_TIMEOUT_MS,
            )
            status = response.status if response else "unknown"
            _emit("navigate", url=url, http_status=status)
            return {"status": "ok", "url": url, "http_status": status}
        except PlaywrightTimeoutError:
            err_msg = f"Navigation to '{url}' failed after {ACTION_TIMEOUT_MS//1000}s timeout waiting for networkidle."
            _emit_error("navigate", err_msg, url=url)
            raise TimeoutError(err_msg)
        except Exception as e:
            _emit_error("navigate", str(e), url=url)
            raise RuntimeError(f"Navigation to '{url}' failed: {str(e)}")

    async def _async_click(self, selector: str) -> dict:
        try:
            # Playwright locator API: handles CSS, XPath, and text= pseudo-selectors
            locator = self._page.locator(selector).first
            await locator.wait_for(state="visible", timeout=ACTION_TIMEOUT_MS)
            await locator.scroll_into_view_if_needed(timeout=ACTION_TIMEOUT_MS)
            await locator.click(timeout=ACTION_TIMEOUT_MS)
            _emit("click", selector=selector)
            return {"status": "ok", "selector": selector}
        except PlaywrightTimeoutError:
            err_msg = f"Element selector '{selector}' not found or actionable after {ACTION_TIMEOUT_MS//1000}s timeout"
            _emit_error("click", err_msg, selector=selector)
            raise TimeoutError(err_msg)
        except Exception as e:
            _emit_error("click", str(e), selector=selector)
            raise RuntimeError(f"Failed to click selector '{selector}': {str(e)}")

    async def _async_type(self, selector: str, text: str) -> dict:
        try:
            locator = self._page.locator(selector).first
            await locator.wait_for(state="visible", timeout=ACTION_TIMEOUT_MS)
            await locator.focus(timeout=ACTION_TIMEOUT_MS)
            # Triple-click selects existing text; fill() then replaces it cleanly
            await locator.fill(text, timeout=ACTION_TIMEOUT_MS)
            _emit("type", selector=selector, text_length=len(text))
            return {"status": "ok", "selector": selector, "chars_typed": len(text)}
        except PlaywrightTimeoutError:
            err_msg = f"Input selector '{selector}' not found or visible after {ACTION_TIMEOUT_MS//1000}s timeout"
            _emit_error("type", err_msg, selector=selector)
            raise TimeoutError(err_msg)
        except Exception as e:
            _emit_error("type", str(e), selector=selector)
            raise RuntimeError(f"Failed to type in selector '{selector}': {str(e)}")

    async def _async_scrape_text(self, selector: str = "body") -> dict:
        try:
            # Wait for the target container to be present before extracting
            locator = self._page.locator(selector).first
            await locator.wait_for(state="visible", timeout=ACTION_TIMEOUT_MS)
            raw_text = await locator.inner_text(timeout=ACTION_TIMEOUT_MS)
            # Normalise whitespace for LLM consumption
            clean = "\n".join(
                line.strip() for line in raw_text.splitlines() if line.strip()
            )
            # Hard cap at 10,000 chars to protect context window (same as browse_web)
            truncated = clean[:10_000]
            _emit(
                "scrape_text",
                selector=selector,
                chars_extracted=len(clean),
                chars_returned=len(truncated),
                truncated=(len(clean) > 10_000),
            )
            return {"status": "ok", "selector": selector, "text": truncated}
        except PlaywrightTimeoutError:
            err_msg = f"Element selector '{selector}' not found or visible after {ACTION_TIMEOUT_MS//1000}s timeout"
            _emit_error("scrape_text", err_msg, selector=selector)
            raise TimeoutError(err_msg)
        except Exception as e:
            _emit_error("scrape_text", str(e), selector=selector)
            raise RuntimeError(f"Failed to scrape text from '{selector}': {str(e)}")

    # ------------------------------------------------------------------
    # Public synchronous API (called by TOOL_REGISTRY wrappers)
    # ------------------------------------------------------------------

    def navigate(self, url: str) -> dict:
        """Navigate to *url* and wait for networkidle. Returns status dict."""
        return self._submit(self._async_navigate(url))

    def click(self, selector: str) -> dict:
        """
        Click the element matching *selector*.

        Supported formats:
          CSS:   "button.submit", "#login-btn", "[data-testid='send']"
          XPath: "xpath=//button[contains(text(),'Sign In')]"
          Text:  "text=Sign In"   or   ":text('Sign In')"
          Role:  "role=button[name='Submit']"
        """
        return self._submit(self._async_click(selector))

    def type(self, selector: str, text: str) -> dict:
        """Focus the field at *selector* and type *text* into it."""
        return self._submit(self._async_type(selector, text))

    def scrape_text(self, selector: str = "body") -> dict:
        """Extract inner text from *selector* (default: full body)."""
        return self._submit(self._async_scrape_text(selector))


# ---------------------------------------------------------------------------
# Module-level singleton — lazily initialised
# ---------------------------------------------------------------------------

_agent: Optional[PlaywrightBrowserAgent] = None
_agent_lock = threading.Lock()


def _get_agent() -> PlaywrightBrowserAgent:
    """Return the shared singleton, creating it on first call."""
    global _agent
    if _agent is None:
        with _agent_lock:
            if _agent is None:
                _agent = PlaywrightBrowserAgent()
    return _agent


def shutdown_browser_agent() -> None:
    """
    Gracefully shut down the persistent browser context.
    Call this from tools.py shutdown_agent_tools() to clean up on daemon exit.
    """
    global _agent
    if _agent is not None:
        _agent.shutdown()
        _agent = None


# ---------------------------------------------------------------------------
# TOOL_REGISTRY-compatible synchronous wrappers
# ---------------------------------------------------------------------------

def browser_navigate(url: str) -> dict:
    """
    Navigate the JARVIS browser to *url* and wait for the page to fully load.

    Waits for networkidle state (no pending network requests for 500ms).
    Maximum timeout: 10 seconds.
    """
    return _get_agent().navigate(url)


def browser_click(selector: str) -> dict:
    """
    Click the element matching *selector* in the current browser page.

    Waits for element to be visible and actionable before clicking.
    Supports CSS selectors, XPath (xpath=...), text matching (text=...),
    and ARIA roles (role=button[name='...']).
    Maximum wait timeout: 10 seconds.
    """
    return _get_agent().click(selector)


def browser_type(selector: str, text: str) -> dict:
    """
    Type *text* into the input/password field matching *selector*.

    Focuses the field, clears any existing content, then fills with *text*.
    Maximum wait timeout: 10 seconds.
    """
    return _get_agent().type(selector, text)


def browser_scrape_text(selector: str = "body") -> dict:
    """
    Extract visible inner text from the element matching *selector*.

    Defaults to full page body. Returns up to 10,000 characters so the LLM
    can read job descriptions, form states, or page change confirmations.
    Maximum wait timeout: 10 seconds.
    """
    return _get_agent().scrape_text(selector)


# ---------------------------------------------------------------------------
# Legacy browse_web — kept for backward compatibility with existing tool
# registry entry and the original headless-scrape use case.
# ---------------------------------------------------------------------------

def browse_web(url: str) -> str:
    """
    Headless scrape: navigate to *url* and return cleaned Markdown content.

    Uses a disposable sync Playwright context (no session persistence).
    This is intentionally separate from PlaywrightBrowserAgent — it is
    stateless, fast, and suited for read-only LLM research tasks.
    """
    logger.info("browser_agent_navigating", url=url)
    html_content = ""

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=15_000)
            html_content = page.content()
            browser.close()
    except Exception as e:
        logger.error("browser_navigation_failed", url=url, error=str(e))
        return f"Error: Failed to navigate to {url}. Details: {str(e)}"

    try:
        soup = BeautifulSoup(html_content, "html.parser")
        for tag in soup(["script", "style", "noscript", "iframe", "svg", "nav", "footer"]):
            tag.extract()
        markdown_text = markdownify.markdownify(str(soup), heading_style="ATX")
        clean_md = "\n".join(
            line.strip() for line in markdown_text.splitlines() if line.strip()
        )
        return clean_md[:10_000]
    except Exception as e:
        logger.error("html_parsing_failed", error=str(e))
        return "Error: Failed to parse the website content."