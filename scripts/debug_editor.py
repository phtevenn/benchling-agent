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

        # --- Toolbar dropdown buttons ---
        # Button 11 has class mediocre-toolbar-dropdownBtn and may be the
        # list-type selector. Click it and capture what options appear.
        print("\n=== Toolbar dropdown buttons ===")
        buttons = page.locator(".mediocre-toolbar button").all()
        dropdown_indices = [
            i for i, btn in enumerate(buttons)
            if "dropdown" in (btn.get_attribute("class") or "")
        ]
        print(f"  Dropdown buttons at indices: {dropdown_indices}")
        for idx in dropdown_indices:
            btn = buttons[idx]
            text = (btn.inner_text() or "").strip()
            cls = btn.get_attribute("class") or ""
            print(f"\n  Clicking button [{idx}] text={text!r} class={cls!r}")
            try:
                btn.click()
                page.wait_for_timeout(800)
                # Capture any open dropdown/menu
                for sel in (".dropdown-menu", ".dropdown.open ul", "[role='menu']",
                            "[role='listbox']", ".popover", ".tooltip"):
                    loc = page.locator(sel)
                    if loc.count() > 0:
                        raw = loc.first.inner_text().strip()
                        if raw:
                            print(f"    Menu via {sel!r}:\n{raw}")
                            break
                else:
                    print("    (no recognisable menu appeared)")
                page.keyboard.press("Escape")
                page.wait_for_timeout(400)
            except Exception as e:
                print(f"    Error: {e}")

        input("\nDone. Press Enter to close the browser …")

    finally:
        browser.close()


if __name__ == "__main__":
    main()
