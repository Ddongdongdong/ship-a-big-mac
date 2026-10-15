"""Optional browser acceptance: pip install playwright Pillow; use installed Chrome."""

import argparse
from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=(ROOT / "docs/index.html").as_uri())
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as temp, sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width":1440,"height":1000})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(args.url)
        assert page.locator("#receipt-total").inner_text() == "¥171.60"
        page.locator('[data-strategy="省预算"]').click()
        assert page.locator("#receipt-total").inner_text() == "¥129.70"
        for scene, heading in (("major","RELEASE UNLOCKED"),("hotfix","HOTFIX HERO"),("sprint","SPRINT COMPLETE"),("comeback","BACK TO GREEN")):
            page.locator(f'[data-scene="{scene}"]').click()
            assert heading in page.locator("#achievement-card").inner_text()
        page.locator("#release-version").fill('<img src=x onerror=1>')
        assert page.locator("#achievement-card img").count() == 0
        page.locator("#release-version").fill("v3.1.0")
        for button, filename in (("#download-png","card.png"),("#download-card","card.svg"),("#download-receipt","receipt.svg")):
            with page.expect_download() as info:
                page.locator(button).click()
            target = Path(temp) / filename
            info.value.save_as(target)
            if filename.endswith(".png"):
                assert Image.open(target).size == (1080,1350)
            else:
                svg = target.read_text(encoding="utf-8")
                ET.fromstring(svg)
                assert "v3.1.0" in svg
                assert "MCP VERIFIED" not in svg
        page.evaluate("Object.defineProperty(navigator,'clipboard',{value:{writeText:async()=>{throw Error('denied')}},configurable:true})")
        page.locator("#copy-share").click()
        page.locator("#copy-fallback").wait_for(state="visible")
        assert "虚构" in page.locator("#copy-text").input_value()
        page.locator("#copy-command").click()
        assert "celebrate --demo" in page.locator("#copy-text").input_value()
        page.locator("#people").fill("12")
        page.locator("#budget").fill("60")
        for button in ("#download-png","#download-card","#download-receipt","#copy-share"):
            assert page.locator(button).is_disabled()
        assert "至少需要" in page.locator("#receipt-lines").inner_text()
        for width in (320,390,768,1024,1440):
            page.set_viewport_size({"width":width,"height":844})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), width
        assert not errors, errors
        browser.close()
    print("Browser acceptance passed: themes, strategies, escaped input, PNG/SVG, clipboard fallback, budget failure, 5 widths.")


if __name__ == "__main__":
    main()
