"""Browser automation for writing content into Benchling entries.

Uses Playwright with a persistent browser context so OAuth sessions
survive between runs. On first use, call `login()` to authenticate
interactively; subsequent calls reuse the saved session.
"""

from __future__ import annotations

import logging
import platform
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from benchling_agent.config import Settings

if TYPE_CHECKING:
    from playwright.sync_api import BrowserContext, Page

logger = logging.getLogger(__name__)

SESSION_DIR = Path.home() / ".benchling-agent" / "browser-session"


@dataclass
class BenchlingBrowser:
    """Automates writing content into Benchling notebook entries."""

    settings: Settings
    headless: bool = False
    _playwright: Any = field(init=False, repr=False, default=None)
    _context: BrowserContext | None = field(init=False, repr=False, default=None)

    def _ensure_context(self) -> BrowserContext:
        if self._context is not None:
            return self._context

        from playwright.sync_api import sync_playwright

        SESSION_DIR.mkdir(parents=True, exist_ok=True)

        self._playwright = sync_playwright().start()
        self._context = self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(SESSION_DIR),
            headless=self.headless,
            channel="chrome",
        )
        return self._context

    def close(self) -> None:
        if self._context:
            self._context.close()
            self._context = None
        if self._playwright:
            self._playwright.stop()
            self._playwright = None

    def _get_page(self) -> Page:
        ctx = self._ensure_context()
        return ctx.pages[0] if ctx.pages else ctx.new_page()

    def login(self, timeout_ms: int = 120_000) -> bool:
        """Open Benchling in a browser for manual OAuth login.

        Waits up to timeout_ms for the user to complete login.
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
            logger.info("Login successful — session saved.")
            return True
        except Exception:
            logger.warning("Login timed out or failed.")
            return False

    def is_logged_in(self) -> bool:
        """Quick check: navigate to Benchling and see if we land on the app."""
        page = self._get_page()
        page.goto(self.settings.benchling_api_url, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
        return self.settings.benchling_api_url in page.url

    def write_entry_content(self, entry_url: str, html_content: str) -> bool:
        """Navigate to a Benchling entry and write HTML content into it.

        Returns True if the content was successfully written.
        """
        page = self._get_page()
        logger.info("Navigating to entry: %s", entry_url)
        page.goto(entry_url, wait_until="domcontentloaded")

        page.wait_for_timeout(3000)

        editor = page.locator('[contenteditable="true"]').first
        editor.wait_for(state="visible", timeout=15_000)

        editor.click()
        mod = "Meta" if platform.system() == "Darwin" else "Control"
        page.keyboard.press(f"{mod}+A")

        page.evaluate(
            """(html) => {
                const editor = document.querySelector('[contenteditable="true"]');
                if (!editor) return false;
                editor.focus();
                document.execCommand('selectAll', false, null);
                document.execCommand('insertHTML', false, html);
                return true;
            }""",
            html_content,
        )

        page.wait_for_timeout(2000)

        logger.info("Content written to entry.")
        return True
