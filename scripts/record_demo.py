"""Record 30 seconds of real offline browser interaction as WebM and GIF.

Development dependencies: playwright, Pillow; requires installed Chrome.
No account connection, credentials, or live quotes are involved.
"""

import io
from pathlib import Path
import time
import shutil
import subprocess

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main():
    recording = ROOT / ".mcd/recording"
    recording.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        context = browser.new_context(viewport={"width":1280,"height":900},record_video_dir=str(recording),record_video_size={"width":1280,"height":900},reduced_motion="reduce")
        page = context.new_page()
        page.goto((ROOT / "docs/index.html").as_uri())
        page.evaluate("document.body.style.zoom = '0.85'")
        page.screenshot(path=str(ROOT / "assets/playground-hero.png"))
        page.evaluate("""() => { const label=document.createElement('div');label.id='recording-caption';label.textContent='实际网页操作 · 离线虚构菜单 · 未下单';label.style='position:fixed;bottom:18px;left:50%;transform:translateX(-50%);background:#252821;color:#fff4da;padding:12px 22px;border-radius:99px;z-index:1000;font:13px Arial,Microsoft YaHei;box-shadow:0 4px 20px #0003;white-space:nowrap';document.body.append(label) }""")
        def caption(text):
            page.locator("#recording-caption").evaluate("(el,text)=>el.textContent=text",text)
        def scene():
            page.locator('[data-scene="comeback"]').click()
            caption("01 · 构建终于变绿，选一顿绝地反击庆功餐")
        def version():
            page.locator("#release-version").fill("v3.1.0")
            caption("02 · 这张成就卡，属于你的 Release")
        def budget():
            page.locator("#people").fill("6")
            page.locator("#budget").fill("240")
            caption("03 · 6 位队友，总预算 240 元 · 金额为示意")
        def strategy():
            page.locator('[data-strategy="省预算"]').click()
            caption("04 · 试试不同搭配，所有示例结果与 Python 规划器对齐")
        def generate():
            page.locator('#planner-form button[type="submit"]').click()
            caption("05 · 生成成就卡：这次交付，值得庆祝")
        def download():
            with page.expect_download() as info:
                page.locator("#download-png").click()
            info.value.save_as(recording / "actual-export.png")
            caption("06 · 实际导出 1080 × 1350 PNG，分享给队友")
        def finish():
            page.locator("#achievement-card").scroll_into_view_if_needed()
            caption("Ship a Big Mac · 免费试玩，喜欢就送它一颗 Star")
        events = [(4,lambda:page.locator('.hero-actions a[href="#demo"]').click()),(7,scene),(10,version),(13,budget),(16,strategy),(19,generate),(23,download),(26,finish)]
        frames, durations = [], []
        started = time.monotonic()
        next_event = 0
        previous = started
        while time.monotonic()-started < 30:
            elapsed = time.monotonic()-started
            while next_event < len(events) and elapsed >= events[next_event][0]:
                events[next_event][1]()
                next_event += 1
            now = time.monotonic()
            if frames:
                durations.append(max(10,int((now-previous)*1000)))
            previous = now
            frame = Image.open(io.BytesIO(page.screenshot())).convert("RGB")
            frame.thumbnail((960,675))
            frames.append(frame.quantize(colors=128))
            page.wait_for_timeout(210)
        durations.append(max(10,30000-sum(durations)))
        frames[0].save(ROOT / "assets/celebrate-demo.gif",save_all=True,append_images=frames[1:],duration=durations,loop=0,optimize=True)
        video = page.video
        context.close()
        video.save_as(str(ROOT / "assets/celebrate-demo.webm"))
        browser.close()
    print(f"Recorded {len(frames)} actual browser frames, approximately 30 seconds, with a successful PNG download.")
    encoder = shutil.which("ffmpeg")
    if encoder:
        subprocess.run([encoder, "-v", "error", "-y", "-i", str(ROOT / "assets/celebrate-demo.webm"), "-t", "30", "-vcodec", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-crf", "20", str(ROOT / "assets/celebrate-demo.mp4")], check=True)


if __name__ == "__main__":
    main()
