"""
Einmaliger Check der Pokemon-Center-Kategorie für GitHub Actions.
Das Topic kommt aus dem GitHub-Secret NTFY_TOPIC.
"""
 
import json
import os
import sys
from pathlib import Path
 
import requests
from playwright.sync_api import sync_playwright
 
URL = "https://www.pokemoncenter.com/de-de/category/30th-celebration"
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "")
STATE_FILE = Path("state.json")
PRODUCT_LINK_SELECTOR = 'a[href*="/product/"]'
 
 
def notify(title: str, message: str) -> None:
    if not NTFY_TOPIC:
        print("NTFY_TOPIC fehlt!")
        return
    requests.post(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=message.encode("utf-8"),
        headers={"Title": title, "Click": URL, "Priority": "high"},
        timeout=15,
    )
 
 
def fetch_products() -> dict:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            locale="de-DE",
            viewport={"width": 1400, "height": 1000},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        try:
            page.goto(URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_selector(PRODUCT_LINK_SELECTOR, timeout=30000)
            for _ in range(6):
                page.mouse.wheel(0, 2500)
                page.wait_for_timeout(800)
 
            items = page.eval_on_selector_all(
                PRODUCT_LINK_SELECTOR,
                "els => els.map(e => [e.href, (e.innerText || e.getAttribute('aria-label') || '').trim()])",
            )
            products = {}
            for href, text in items:
                href = href.split("?")[0]
                if href not in products or (text and not products[href]):
                    products[href] = text.replace("\n", " ")
            return products
        except Exception:
            print("Seitentitel:", page.title())
            print("Textanfang:", page.inner_text("body")[:500])
            raise
        finally:
            browser.close()
 
 
def main() -> None:
    try:
        current = fetch_products()
    except Exception as e:
        print(f"Fehler beim Abruf: {e}")
        sys.exit(0)  # kein Fehlerstatus, damit GitHub keine Mail-Flut schickt
 
    state = json.loads(STATE_FILE.read_text("utf-8")) if STATE_FILE.exists() else {}
    previous = state.get("products")
 
    if previous is None:
        print(f"Startzustand: {len(current)} Produkte")
        notify("Tracker gestartet", f"{len(current)} Produkte gefunden.")
    else:
        new = {u: n for u, n in current.items() if u not in previous}
        if new:
            lines = [f"- {n or u}" for u, n in list(new.items())[:10]]
            print(f"NEU: {len(new)}")
            notify(f"{len(new)} neue(s) Produkt(e)!", "\n".join(lines))
        else:
            print(f"Keine Änderung ({len(current)} Produkte)")
 
    STATE_FILE.write_text(
        json.dumps({"products": current}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
 
 
if __name__ == "__main__":
    main()
