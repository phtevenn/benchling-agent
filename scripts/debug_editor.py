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
        # Click each candidate button on a fresh line and check if the line
        # becomes a list item. Undo after each attempt.
        print("\n=== Identifying list toolbar buttons ===")
        editor = page.locator(BODY_SELECTOR).first
        editor.click()
        page.wait_for_timeout(500)

        # Candidate indices: non-dropdown buttons after the heading dropdown [4]
        candidates = [5, 6, 7, 8, 9, 12, 13, 14, 15, 16]
        buttons = page.locator(".mediocre-toolbar button").all()

        for idx in candidates:
            if idx >= len(buttons):
                continue
            btn = buttons[idx]

            # Move to end, fresh line
            page.keyboard.press("Control+End")
            page.wait_for_timeout(200)
            page.keyboard.press("Enter")
            page.wait_for_timeout(300)

            # Click the button
            try:
                btn.click()
                page.wait_for_timeout(400)
            except Exception as e:
                print(f"  [{idx}] click error: {e}")
                continue

            # Check what the current line looks like in the DOM
            # Look for list-item indicators: ul, ol, li elements in editor
            has_list = page.evaluate("""() => {
                const editor = document.querySelector(
                    'div.editable[contenteditable="true"]'
                    + ':not(.mediocre-titleEditor-titleEditable)'
                    + ':not(.hiddenFocusEditable)'
                );
                if (!editor) return 'no editor';
                const sel = window.getSelection();
                if (!sel || !sel.anchorNode) return 'no selection';
                let node = sel.anchorNode;
                // Walk up to find list context
                while (node && node !== editor) {
                    const tag = node.nodeName ? node.nodeName.toLowerCase() : '';
                    const cls = node.className || '';
                    if (tag === 'li' || tag === 'ul' || tag === 'ol'
                            || cls.includes('list') || cls.includes('bullet')) {
                        return tag + ' class=' + cls;
                    }
                    node = node.parentNode;
                }
                // Report the immediate parent element class
                let n = sel.anchorNode;
                if (n.nodeType === 3) n = n.parentNode;
                return 'no list — nearest: ' + n.nodeName + ' class=' + (n.className || '');
            }""")
            print(f"  [{idx}] → {has_list}")

            # Undo and move back
            page.keyboard.press(f"{_MOD}+Z")
            page.wait_for_timeout(200)
            page.keyboard.press(f"{_MOD}+Z")
            page.wait_for_timeout(200)

        input("\nDone. Press Enter to close the browser …")

    finally:
        browser.close()


if __name__ == "__main__":
    main()
