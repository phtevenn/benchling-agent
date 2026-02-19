"""Diagnostic script for inspecting Benchling's mediocre editor.

Run with:
    uv run python scripts/debug_editor.py <entry-url>

Prints:
  - All toolbar buttons (index, aria-label, title, text)
  - All slash-command options available in the dropdown
  - Current editor focus state

Useful for verifying toolbar indices and slash command labels before
updating hard-coded values in browser.py.
"""

import platform
import sys

from benchling_agent.clients.browser import BODY_SELECTOR, BenchlingBrowser
from benchling_agent.config import get_settings

_MOD = "Meta" if platform.system() == "Darwin" else "Control"


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: uv run python scripts/debug_editor.py <entry-url>")
        sys.exit(1)

    entry_url = sys.argv[1]
    settings = get_settings()
    browser = BenchlingBrowser(settings=settings, headless=False)

    try:
        page = browser._get_page()
        print(f"Navigating to {entry_url} …")
        page.goto(entry_url, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        # --- Toolbar buttons ---
        buttons = page.locator(".mediocre-toolbar button").all()
        print(f"\n=== Toolbar buttons ({len(buttons)} total) ===")
        for i, btn in enumerate(buttons):
            aria = btn.get_attribute("aria-label") or ""
            title = btn.get_attribute("title") or ""
            text = (btn.inner_text() or "").strip()
            cls = btn.get_attribute("class") or ""
            print(f"  [{i:2d}]  aria-label={aria!r:30s}  title={title!r:30s}  text={text!r:10s}  class={cls!r}")

        # --- Slash command options ---
        # Reproduce the same focus sequence used in write_entry_content so
        # the slash command actually fires.
        print("\n=== Slash command options ===")
        editor = page.locator(BODY_SELECTOR).first
        editor.wait_for(state="visible", timeout=10_000)
        editor.click()
        page.wait_for_timeout(2000)   # match write_entry_content's post-click wait

        # Move to a fresh empty line at the end of the document
        page.keyboard.press("Control+End")
        page.wait_for_timeout(300)
        page.keyboard.press("Enter")
        page.wait_for_timeout(500)

        # Type "/" to trigger the slash command menu
        page.keyboard.type("/")
        page.wait_for_timeout(2000)   # give it plenty of time to open

        # Try multiple selectors for the dropdown
        found = False
        for sel in (".attachDropdown", "[data-testid='AttachDropdown-root']",
                    "[role='listbox']", ".dropdown.open"):
            loc = page.locator(sel)
            if loc.count() > 0:
                print(f"  Dropdown found via selector: {sel!r}")
                # Grab all text from every child element
                children = loc.locator("*").all()
                texts = set()
                for child in children:
                    try:
                        t = child.inner_text().strip()
                        if t and len(t) < 80:   # skip long/empty strings
                            texts.add(t)
                    except Exception:
                        pass
                # Also dump raw text as fallback
                raw = loc.inner_text().strip()
                print(f"  Raw dropdown text:\n{raw}\n")
                found = True
                break

        if not found:
            print("  No dropdown found with any known selector.")
            print("  Page URL:", page.url)
            # Last resort: dump all visible text on the page
            print("  Visible text sample:", page.inner_text("body")[:500])

        # Close the dropdown
        page.keyboard.press("Escape")
        page.wait_for_timeout(500)
        page.keyboard.press("Backspace")

        # --- Identify list buttons ---
        # Click each candidate button on a line with typed content and check
        # whether that content ends up inside a <li> element in the DOM.
        # (window.getSelection() is unreliable after toolbar clicks because
        # the button briefly steals focus; DOM inspection is definitive.)
        print("\n=== Identifying list toolbar buttons ===")

        # Candidate indices: non-dropdown icon buttons
        candidates = [5, 6, 7, 8, 9, 12, 13, 14, 15, 16]
        buttons = page.locator(".mediocre-toolbar button").all()

        for idx in candidates:
            if idx >= len(buttons):
                continue
            btn = buttons[idx]

            # Re-focus editor before each attempt
            editor_loc = page.locator(BODY_SELECTOR).first
            editor_loc.click()
            page.wait_for_timeout(300)

            # Go to end of document, open a fresh line, type a unique marker
            page.keyboard.press(f"{_MOD}+End")
            page.wait_for_timeout(200)
            page.keyboard.press("Enter")
            page.wait_for_timeout(300)
            marker = f"TEST{idx}"
            page.keyboard.type(marker)
            page.wait_for_timeout(200)

            # Click the button
            try:
                btn.click()
                page.wait_for_timeout(600)
            except Exception as e:
                print(f"  [{idx}] click error: {e}")
                page.keyboard.press("Escape")
                page.wait_for_timeout(200)
                for _ in range(4):
                    page.keyboard.press(f"{_MOD}+Z")
                    page.wait_for_timeout(150)
                continue

            # DOM-based check: is the marker text inside any <li>?
            result = page.evaluate(
                """(marker) => {
                    const ed = document.querySelector(
                        'div.editable[contenteditable="true"]'
                        + ':not(.mediocre-titleEditor-titleEditable)'
                        + ':not(.hiddenFocusEditable)'
                    );
                    if (!ed) return 'no editor';
                    const lis = ed.querySelectorAll('li');
                    for (const li of lis) {
                        if (li.textContent.includes(marker)) {
                            return 'IN LIST: ' + li.parentNode.nodeName
                                + ' (li count=' + lis.length + ')';
                        }
                    }
                    return 'not in list (total li: ' + lis.length + ')';
                }""",
                marker,
            )
            print(f"  [{idx}] → {result}")

            # Close any dialog that may have opened (e.g. link dialog for [9])
            page.keyboard.press("Escape")
            page.wait_for_timeout(200)
            # Undo button effect + typed text + Enter
            for _ in range(4):
                page.keyboard.press(f"{_MOD}+Z")
                page.wait_for_timeout(150)

        input("\nDone. Press Enter to close the browser …")

    finally:
        browser.close()


if __name__ == "__main__":
    main()
