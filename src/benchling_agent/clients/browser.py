"""Browser automation for writing content into Benchling entries.

Uses Playwright with explicit storage state management so OAuth sessions
survive between runs. On first use, call `login()` to authenticate
interactively; the session cookies are saved to disk and reused.

Content is written via keyboard actions and toolbar buttons to work with
Benchling's custom "mediocre" editor, which strips raw HTML on paste.
"""

from __future__ import annotations

import logging
import platform
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from benchling_agent.clients.content_parser import (
    BlockType,
    EditorAction,
    TextSegment,
    parse_content,
)
from benchling_agent.config import Settings

if TYPE_CHECKING:
    from playwright.sync_api import Browser, BrowserContext, Page

logger = logging.getLogger(__name__)

STORAGE_DIR = Path.home() / ".benchling-agent"
STORAGE_STATE_PATH = STORAGE_DIR / "browser-state.json"

BODY_SELECTOR = (
    'div.editable[contenteditable="true"]'
    ":not(.mediocre-titleEditor-titleEditable)"
    ":not(.hiddenFocusEditable)"
)

_TOOLBAR_INDEX_UL = 14
_TOOLBAR_INDEX_OL = 15
_MOD = "Meta" if platform.system() == "Darwin" else "Control"

_SLASH_HEADING_MAP = {
    BlockType.HEADER1: "Header 1",
    BlockType.HEADER2: "Header 2",
    BlockType.SUBHEADER: "Subheader 1",
}


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

        self._context = self._browser.new_context(
            permissions=["clipboard-read", "clipboard-write"],
            viewport={"width": 1920, "height": 1080},
            **kwargs,
        )
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
        """Open Benchling in a browser for manual OAuth login."""
        page = self._get_page()
        page.goto(self.settings.benchling_api_url)

        logger.info(
            "Waiting for login — please authenticate in the browser window."
        )
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
        """Navigate to Benchling and check if we land on the app."""
        if not STORAGE_STATE_PATH.exists():
            return False
        page = self._get_page()
        page.goto(
            self.settings.benchling_api_url, wait_until="domcontentloaded"
        )
        page.wait_for_timeout(5000)
        logged_in = self.settings.benchling_api_url in page.url
        logger.info(
            "Login check: url=%s, logged_in=%s", page.url, logged_in
        )
        return logged_in

    # ------------------------------------------------------------------
    # Keyboard-driven content writing
    # ------------------------------------------------------------------

    def _type_segments(self, page: Page, segments: list[TextSegment]) -> None:
        """Type inline text segments, toggling bold with Cmd/Ctrl+B."""
        for seg in segments:
            if seg.bold:
                page.keyboard.press(f"{_MOD}+B")
            page.keyboard.type(seg.text)
            if seg.bold:
                page.keyboard.press(f"{_MOD}+B")

    def _slash_command(self, page: Page, label: str) -> None:
        """Invoke a slash command by typing '/' and clicking the menu item."""
        page.keyboard.type("/")
        page.wait_for_timeout(800)
        option = page.locator(f'.attachDropdown >> text="{label}"').first
        option.click()
        page.wait_for_timeout(400)

    def _toggle_bullet_list(self, page: Page) -> None:
        """Click the unordered-list toolbar button."""
        buttons = page.locator(".mediocre-toolbar button").all()
        if len(buttons) > _TOOLBAR_INDEX_UL:
            buttons[_TOOLBAR_INDEX_UL].click()
            page.wait_for_timeout(300)

    def _right_click_col(self, page: Page, col_index: int) -> None:
        """Scroll a column header into view and right-click it."""
        col = page.locator(
            f'[data-testid="TableAxisCell-columnheader-{col_index}"]'
        )
        col.scroll_into_view_if_needed()
        page.wait_for_timeout(300)
        col.click(button="right")
        page.wait_for_timeout(600)

    def _click_ctx_item(self, page: Page, label: str) -> None:
        """Click a context menu item via JS to bypass visibility checks."""
        page.evaluate(
            """(label) => {
                const items = document.querySelectorAll(
                    '.contextMenu .context-item'
                );
                for (const item of items) {
                    if (item.textContent.trim() === label) {
                        item.dispatchEvent(
                            new MouseEvent('click', {bubbles: true})
                        );
                        return;
                    }
                }
            }""",
            label,
        )
        page.wait_for_timeout(400)

    def _write_table(self, page: Page, table_data: list[list[str]]) -> None:
        """Insert a Benchling table widget and populate it via TSV paste.

        table_data[0] is the header row (used for column names).
        table_data[1:] are data rows.
        """
        if not table_data or len(table_data) < 2:
            return

        header = table_data[0]
        data_rows = table_data[1:]
        num_cols = len(header)
        num_data_rows = len(data_rows)

        self._slash_command(page, "Table")
        page.wait_for_timeout(2000)

        # Add extra columns (default table has 2)
        for i in range(max(0, num_cols - 2)):
            self._right_click_col(page, 1 + i)
            self._click_ctx_item(page, "Insert column right")
            page.wait_for_timeout(400)

        # Rename columns to header values
        for i, name in enumerate(header):
            self._right_click_col(page, i)
            self._click_ctx_item(page, "Rename column")
            page.wait_for_timeout(300)
            page.keyboard.type(name)
            page.keyboard.press("Enter")
            page.wait_for_timeout(400)

        # Add extra rows (default table has 2)
        extra = num_data_rows - 2
        if extra > 0:
            add_input = page.locator(
                ".mediocre-tableEditable-addRowInput"
            ).first
            add_input.fill(str(extra))
            page.wait_for_timeout(200)
            page.locator('button:text("Add rows")').first.click()
            page.wait_for_timeout(800)

        # Build TSV string and paste into first cell
        tsv = "\n".join("\t".join(row) for row in data_rows)
        first_cell = page.locator("td.cell.cell-contents").first
        first_cell.click()
        page.wait_for_timeout(400)

        page.evaluate(
            "async (tsv) => { await navigator.clipboard.writeText(tsv); }",
            tsv,
        )
        page.wait_for_timeout(200)
        page.keyboard.press(f"{_MOD}+V")
        page.wait_for_timeout(2000)

        # Exit the table: click the main editor body below the table
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
        editor = page.locator(BODY_SELECTOR).first
        # Click at the bottom of the editor to place cursor after the table
        box = editor.bounding_box()
        if box:
            page.mouse.click(
                box["x"] + box["width"] / 2,
                box["y"] + box["height"] - 5,
            )
        page.wait_for_timeout(500)
        page.keyboard.press("Enter")
        page.wait_for_timeout(300)

    def _execute_actions(
        self, page: Page, actions: list[EditorAction]
    ) -> None:
        """Execute a sequence of editor actions via keyboard interactions."""
        in_bullet = False
        current_indent = 0

        for action in actions:
            if action.block_type == BlockType.BLANK:
                if in_bullet:
                    self._toggle_bullet_list(page)
                    in_bullet = False
                    current_indent = 0
                page.keyboard.press("Enter")
                page.wait_for_timeout(150)
                continue

            if action.block_type in _SLASH_HEADING_MAP:
                if in_bullet:
                    self._toggle_bullet_list(page)
                    in_bullet = False
                    current_indent = 0
                label = _SLASH_HEADING_MAP[action.block_type]
                self._slash_command(page, label)
                self._type_segments(page, action.segments)
                page.keyboard.press("Enter")
                page.wait_for_timeout(200)
                continue

            if action.block_type == BlockType.BULLET:
                if not in_bullet:
                    self._toggle_bullet_list(page)
                    in_bullet = True
                    current_indent = 0

                target_indent = action.indent_level
                while current_indent < target_indent:
                    page.keyboard.press("Tab")
                    page.wait_for_timeout(100)
                    current_indent += 1
                while current_indent > target_indent:
                    page.keyboard.press("Shift+Tab")
                    page.wait_for_timeout(100)
                    current_indent -= 1

                self._type_segments(page, action.segments)
                page.keyboard.press("Enter")
                page.wait_for_timeout(150)
                continue

            if action.block_type == BlockType.TABLE:
                if in_bullet:
                    self._toggle_bullet_list(page)
                    in_bullet = False
                    current_indent = 0
                self._write_table(page, action.table_data)
                continue

            # PARAGRAPH
            if in_bullet:
                self._toggle_bullet_list(page)
                in_bullet = False
                current_indent = 0
            self._type_segments(page, action.segments)
            page.keyboard.press("Enter")
            page.wait_for_timeout(150)

        # Exit bullet mode if still active at the end
        if in_bullet:
            self._toggle_bullet_list(page)

    def write_entry_content(self, entry_url: str, content: str) -> bool:
        """Navigate to a Benchling entry and write formatted content.

        Parses the markdown content into editor actions and executes them
        using keyboard interactions and toolbar buttons.

        Returns True if the content was successfully written.
        """
        if not STORAGE_STATE_PATH.exists():
            logger.warning(
                "No saved browser session. "
                "Run 'benchling-agent login' first."
            )
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
        editor = page.locator(BODY_SELECTOR).first
        editor.wait_for(state="visible", timeout=30_000)
        logger.info("Editor found, clicking to focus...")
        editor.click()
        page.wait_for_timeout(1000)

        actions = parse_content(content)
        logger.info("Parsed %d editor actions from content", len(actions))
        self._execute_actions(page, actions)

        logger.info("Waiting for Benchling autosave...")
        page.wait_for_timeout(5000)
        logger.info("Content written to entry successfully.")
        return True
