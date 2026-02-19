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

import sys

from benchling_agent.clients.browser import BODY_SELECTOR, BenchlingBrowser
from benchling_agent.config import get_settings


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
        print("\n=== Slash command options ===")
        editor = page.locator(BODY_SELECTOR).first
        editor.wait_for(state="visible", timeout=10_000)
        editor.click()
        page.wait_for_timeout(1000)
        page.keyboard.type("/")
        page.wait_for_timeout(1200)

        dropdown = page.locator(".attachDropdown")
        if dropdown.count() > 0:
            items = dropdown.locator("li, [role='option'], .attachDropdown-item").all()
            if items:
                print(f"  {len(items)} options found:")
                for item in items:
                    print(f"    - {item.inner_text().strip()!r}")
            else:
                # Fallback: dump full text
                print("  Raw dropdown text:")
                print(f"    {dropdown.inner_text()!r}")
        else:
            print("  No .attachDropdown found — slash command may not have opened")

        # Close the dropdown
        page.keyboard.press("Escape")
        page.wait_for_timeout(500)
        page.keyboard.press("Backspace")

        input("\nDone. Press Enter to close the browser …")

    finally:
        browser.close()


if __name__ == "__main__":
    main()
