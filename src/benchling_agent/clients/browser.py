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

    def _refocus_editor(self, page: Page) -> None:
        """Click the editor body to ensure keyboard focus is in the right place."""
        editor = page.locator(BODY_SELECTOR).first
        editor.click()
        page.wait_for_timeout(500)

    def _slash_command(self, page: Page, label: str, max_retries: int = 3) -> None:
        """Invoke a slash command by typing '/' and clicking the menu item.

        The attachDropdown is present in the DOM with class 'open' but
        Playwright's CSS-based visibility check considers it hidden, so we
        use force=True on click. Uses a short per-attempt timeout and retries
        with editor re-focus so a single slow dropdown doesn't crash the run.
        """
        for attempt in range(max_retries):
            page.keyboard.type("/")
            page.wait_for_timeout(1000)
            try:
                page.locator(".attachDropdown").get_by_text(
                    label, exact=True
                ).first.click(force=True, timeout=5000)
                page.wait_for_timeout(400)
                return
            except Exception:
                logger.warning(
                    "Slash command attempt %d/%d failed for %r — retrying",
                    attempt + 1,
                    max_retries,
                    label,
                )
                page.keyboard.press("Escape")
                page.wait_for_timeout(300)
                page.keyboard.press("Backspace")  # remove the stray "/"
                page.wait_for_timeout(200)
                self._refocus_editor(page)
        raise RuntimeError(
            f"Slash command for {label!r} failed after {max_retries} attempts"
        )

    def _toggle_bullet_list(self, page: Page) -> None:
        """Enter unordered bullet list mode via slash command.

        Using a slash command instead of the toolbar button avoids the
        cycling problem: the toolbar button advances through list types
        (○ → ■ → ● → numbered …) on every click, so repeated bullet
        sections would each get a different marker. The slash command
        always creates a fresh unordered list.
        """
        self._slash_command(page, "Bulleted list")

    def _exit_bullet_list(self, page: Page) -> None:
        """Exit the current bullet list.

        After typing the last bullet item and pressing Enter, the cursor
        sits on a new empty bullet. In ProseMirror (which Benchling's
        editor is based on), pressing Enter on an empty list item at
        indent level 0 triggers liftListItem — converting the empty item
        to a plain paragraph outside the list. This is more reliable than
        Backspace, which in ProseMirror typically merges the empty item
        with the previous item and leaves the cursor inside the list.

        Callers must NOT press an extra Enter after this call: the lifted
        paragraph is already a clean empty line they can write into directly.
        """
        page.keyboard.press("Enter")
        page.wait_for_timeout(200)

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
        page.wait_for_timeout(500)
        page.keyboard.press(f"{_MOD}+V")
        page.wait_for_timeout(3000)

        # Exit the table using ProseMirror-aware keyboard navigation.
        # First Escape exits cell-editing mode (TextSelection → still in table).
        # Second Escape selects the table as a whole node (NodeSelection).
        # ArrowDown from a NodeSelection moves the cursor to the block
        # immediately after the node — this is standard ProseMirror behaviour
        # and is reliable regardless of scroll position. The Selection API
        # approach was unreliable because ProseMirror ignores native browser
        # selection changes; it maintains its own internal selection state.
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
        page.keyboard.press("ArrowDown")
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
                    self._exit_bullet_list(page)
                    in_bullet = False
                    current_indent = 0
                    # _exit_bullet_list already landed on an empty paragraph;
                    # don't press Enter again or we'd add an unwanted blank line.
                    continue
                page.keyboard.press("Enter")
                page.wait_for_timeout(150)
                continue

            if action.block_type in _SLASH_HEADING_MAP:
                if in_bullet:
                    self._exit_bullet_list(page)
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
                    self._toggle_bullet_list(page)  # enter bullet mode
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
                    self._exit_bullet_list(page)
                    in_bullet = False
                    current_indent = 0
                self._write_table(page, action.table_data)
                continue

            # PARAGRAPH
            if in_bullet:
                self._exit_bullet_list(page)
                in_bullet = False
                current_indent = 0
            self._type_segments(page, action.segments)
            page.keyboard.press("Enter")
            page.wait_for_timeout(150)

        # Exit bullet mode if still active at the end
        if in_bullet:
            self._exit_bullet_list(page)

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
        page.goto(entry_url, wait_until="domcontentloaded")
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
        page.wait_for_timeout(2000)

        actions = parse_content(content)
        logger.info("Parsed %d editor actions from content", len(actions))
        self._execute_actions(page, actions)

        logger.info("Waiting for Benchling autosave...")
        page.wait_for_timeout(5000)
        logger.info("Content written to entry successfully.")
        return True
