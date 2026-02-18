"""Browser automation for writing content into Benchling entries.

Uses Playwright with explicit storage state management so OAuth sessions
survive between runs. On first use, call `login()` to authenticate
interactively; the session cookies are saved to disk and reused.
"""

from __future__ import annotations

import logging
import platform
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from benchling_agent.config import Settings

if TYPE_CHECKING:
    from playwright.sync_api import Browser, BrowserContext, Page

logger = logging.getLogger(__name__)

STORAGE_DIR = Path.home() / ".benchling-agent"
STORAGE_STATE_PATH = STORAGE_DIR / "browser-state.json"


@dataclass
class BenchlingBrowser:
    """Automates writing content into Benchling notebook entries."""

    settings: Settings
    headless: bool = False
    _playwright: Any = field(init=False, repr=False, default=None)
    _browser: Browser | None = field(init=False, repr=False, default=None)
    _context: BrowserContext | None = field(init=False, repr=False, default=None)

    def _ensure_context(self) -> BrowserContext:
        if self._context is not None:
            return self._context

        from playwright.sync_api import sync_playwright

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=self.headless,
            channel="chrome",
        )

        kwargs: dict[str, Any] = {}
        if STORAGE_STATE_PATH.exists():
            kwargs["storage_state"] = str(STORAGE_STATE_PATH)

        self._context = self._browser.new_context(**kwargs)
        return self._context

    def _save_state(self) -> None:
        if self._context:
            STORAGE_DIR.mkdir(parents=True, exist_ok=True)
            self._context.storage_state(path=str(STORAGE_STATE_PATH))
            logger.info("Browser state saved to %s", STORAGE_STATE_PATH)

    def close(self) -> None:
        if self._context:
            self._context.close()
            self._context = None
        if self._browser:
            self._browser.close()
            self._browser = None
        if self._playwright:
            self._playwright.stop()
            self._playwright = None

    def _get_page(self) -> Page:
        ctx = self._ensure_context()
        return ctx.pages[0] if ctx.pages else ctx.new_page()

    def login(self, timeout_ms: int = 120_000) -> bool:
        """Open Benchling in a browser for manual OAuth login.

        Waits up to timeout_ms for the user to complete login.
        Saves session state on success.
        Returns True if login appears successful.
        """
        page = self._get_page()
        page.goto(self.settings.benchling_api_url)

        logger.info("Waiting for login — please authenticate in the browser window.")
        try:
            page.wait_for_url(
                f"{self.settings.benchling_api_url}/**",
                timeout=timeout_ms,
            )
            self._save_state()
            logger.info("Login successful — session saved.")
            return True
        except Exception:
            logger.warning("Login timed out or failed.")
            return False

    def is_logged_in(self) -> bool:
        """Navigate to Benchling and check if we land on the app (not SSO)."""
        if not STORAGE_STATE_PATH.exists():
            return False
        page = self._get_page()
        page.goto(self.settings.benchling_api_url, wait_until="domcontentloaded")
        page.wait_for_timeout(5000)
        logged_in = self.settings.benchling_api_url in page.url
        logger.info("Login check: url=%s, logged_in=%s", page.url, logged_in)
        return logged_in

    def write_entry_content(self, entry_url: str, html_content: str) -> bool:
        """Navigate to a Benchling entry and write HTML content into it.

        Returns True if the content was successfully written.
        """
        if not STORAGE_STATE_PATH.exists():
            logger.warning("No saved browser session. Run 'benchling-agent login' first.")
            return False

        page = self._get_page()
        logger.info("Navigating to entry: %s", entry_url)
        page.goto(entry_url, wait_until="networkidle")

        logger.info("Page loaded, URL: %s", page.url)

        if self.settings.benchling_api_url not in page.url:
            logger.warning(
                "Redirected away from Benchling (url=%s) — session expired? "
                "Run 'benchling-agent login' to re-authenticate.",
                page.url,
            )
            return False

        logger.info("Waiting for editor to become ready...")
        body_selector = (
            'div.editable[contenteditable="true"]'
            ':not(.mediocre-titleEditor-titleEditable)'
        )
        editor = page.locator(body_selector).first
        editor.wait_for(state="visible", timeout=30_000)
        logger.info("Editor found, clicking to focus...")

        editor.click()
        page.wait_for_timeout(1000)

        mod = "Meta" if platform.system() == "Darwin" else "Control"
        page.keyboard.press(f"{mod}+A")
        page.wait_for_timeout(500)

        injected = page.evaluate(
            """(args) => {
                const [selector, html] = args;
                const editor = document.querySelector(selector);
                if (!editor) return false;
                editor.focus();
                document.execCommand('selectAll', false, null);
                document.execCommand('insertHTML', false, html);
                return true;
            }""",
            [body_selector, html_content],
        )
        logger.info("Content injection result: %s", injected)

        if not injected:
            logger.warning("Failed to inject content into editor.")
            return False

        logger.info("Waiting for Benchling autosave...")
        page.wait_for_timeout(5000)

        logger.info("Content written to entry successfully.")
        return True
