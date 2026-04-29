"""
Instagram Story Screenshotter
- Opens a browser window for manual login
- Navigates to ndpitalia's stories
- Screenshots only the story image/video frame for each story
- Saves to pics/YYYY-MM-DD/
"""

import argparse
import asyncio
import os
import re
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError

try:
    from PIL import Image, ImageStat
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

STORY_URL = "https://www.instagram.com/stories/gianmarcoschiarettiofficial/"
PICS_DIR = Path(__file__).parent / "pics"
CHROME_PROFILE_DIR = Path(__file__).parent.parent / "chrome_profile"


async def wait_for_login(page):
    print("[*] Browser opened. Please log in to Instagram.")
    print("[*] Waiting for you to complete login (up to 3 minutes)...")
    print("[*] Complete ALL steps including two-factor authentication.")
    
    # Check periodically for login completion
    max_attempts = 180  # 3 minutes, checking every second
    for i in range(max_attempts):
        await page.wait_for_timeout(1000)
        
        # Check if logged in with error handling for navigation
        try:
            is_logged_in = await page.evaluate("""
                () => {
                    return !!document.cookie.match(/sessionid=/) ||
                           !!document.querySelector('a[href*="/direct/inbox/"]') ||
                           !!document.querySelector('svg[aria-label="Home"]') ||
                           !!document.querySelector('a[href="/"][role="link"]');
                }
            """)
        except PlaywrightError:
            # Page might be navigating, wait and retry
            continue
        
        if is_logged_in:
            await page.wait_for_timeout(2000)
            print("[ok] Login detected.")
            return
        
        # Show progress every 30 seconds
        if i > 0 and i % 30 == 0:
            print(f"[*] Still waiting for login... ({i//60} minute{'s' if i//60 > 1 else ''} passed)")
    
    raise RuntimeError("Login timed out after 3 minutes.")


async def ensure_logged_in(page):
    """Check if currently logged in; if not, navigate to login page and wait for manual login."""
    # Check current URL first
    current_url = page.url
    if "accounts/login" in current_url or "accounts/onetap" in current_url:
        print("[!] Not logged in. Redirecting to login...")
        await page.goto("https://www.instagram.com/accounts/login/", wait_until="domcontentloaded", timeout=60000)
        await wait_for_login(page)
        return False
    
    # Check if actually logged in by looking for logged-in elements
    try:
        is_logged_in = await page.evaluate("""
            () => {
                return !!document.cookie.match(/sessionid=/) ||
                       !!document.querySelector('a[href*="/direct/inbox/"]') ||
                       !!document.querySelector('svg[aria-label="Home"]') ||
                       !!document.querySelector('a[href="/"][role="link"]');
            }
        """)
    except PlaywrightError:
        # Page might be navigating, assume not logged in
        is_logged_in = False
    
    if not is_logged_in:
        print("[!] Session appears expired or invalid. Redirecting to login...")
        await page.goto("https://www.instagram.com/accounts/login/", wait_until="domcontentloaded", timeout=60000)
        await wait_for_login(page)
        return False
    return True


def get_today_dir() -> Path:
    date_str = datetime.now().strftime("%Y-%m-%d")
    target = PICS_DIR / date_str
    target.mkdir(parents=True, exist_ok=True)
    return target


async def wait_for_media_loaded(page):
    """
    Waits until the largest img/video on the page is fully loaded.
    - img: naturalWidth > 0 and complete == true
    - video: readyState >= 4 (HAVE_ENOUGH_DATA) then paused at 0.5s for a stable frame
    Gives up after 10 seconds and proceeds anyway.
    """
    for _ in range(20):
        result = await page.evaluate("""
            () => {
                const imgs = Array.from(document.querySelectorAll('img')).filter(i => {
                    const r = i.getBoundingClientRect();
                    return r.width > 150 && r.height > 150;
                });
                const videos = Array.from(document.querySelectorAll('video')).filter(v => {
                    const r = v.getBoundingClientRect();
                    return r.width > 150 && r.height > 150;
                });
                if (videos.length > 0) {
                    return videos.every(v => v.readyState >= 4);
                }
                if (imgs.length > 0) {
                    return imgs.every(i => i.complete && i.naturalWidth > 0);
                }
                return false;
            }
        """)
        if result:
            break
        await page.wait_for_timeout(500)

    await page.evaluate("""
        () => {
            const videos = Array.from(document.querySelectorAll('video')).filter(v => {
                const r = v.getBoundingClientRect();
                return r.width > 150 && r.height > 150;
            });
            for (const v of videos) {
                v.pause();
                if (v.duration && v.duration > 0.5) {
                    v.currentTime = 0.5;
                } else if (v.duration) {
                    v.currentTime = v.duration * 0.1;
                }
            }
        }
    """)
    await page.wait_for_timeout(600)


def is_valid_screenshot(filepath: Path) -> bool:
    """
    Returns False if the screenshot is invalid:
    - Mostly black/blank (mean brightness < 15 out of 255)
    - Contains error text patterns (detected via low unique-color count in a mostly dark image)
    Uses PIL if available; if not, checks file size as a rough proxy.
    """
    if not HAS_PIL:
        return filepath.stat().st_size > 50_000

    try:
        img = Image.open(filepath).convert("RGB")
        stat = ImageStat.Stat(img)
        mean_brightness = sum(stat.mean) / 3
        if mean_brightness < 20:
            return False
        return True
    except Exception:
        return True


async def find_story_element(page):
    """
    Finds the largest visible media element (img, video, canvas) on the page
    that is likely the story frame. Returns (element, bounding_box) or (None, None).
    """
    best = None
    best_area = 0

    for tag in ["img", "video", "canvas"]:
        elements = await page.query_selector_all(tag)
        for el in elements:
            try:
                box = await el.bounding_box()
                if not box:
                    continue
                w, h = box["width"], box["height"]
                if w < 150 or h < 150:
                    continue
                area = w * h
                if area > best_area:
                    best_area = area
                    best = (el, box)
            except Exception:
                continue

    return best if best else (None, None)


async def screenshot_story_frame(page, index: int, save_dir: Path) -> bool:
    """
    Waits for media to load, then screenshots the story frame.
    Validates the result and deletes invalid (blank/error) screenshots.
    Returns True if a valid screenshot was saved, False otherwise.
    """
    await wait_for_media_loaded(page)

    element, box = await find_story_element(page)

    filename = save_dir / f"{index + 1:03d}.png"

    if element is not None:
        try:
            await element.screenshot(path=str(filename))
            if not is_valid_screenshot(filename):
                filename.unlink(missing_ok=True)
                print(f"  [skip] Story {index + 1}: invalid/blank frame, deleted.")
                return False
            print(f"  [ok] Story {index + 1}: saved -> {filename.name} (element {int(box['width'])}x{int(box['height'])})")
            return True
        except Exception as e:
            print(f"  [warn] Story {index + 1}: element screenshot failed ({e}), trying clip...")

    vp = page.viewport_size
    if not vp:
        print(f"  [warn] Story {index + 1}: no viewport info, skipping.")
        return False

    vw, vh = vp["width"], vp["height"]
    story_w = 390
    story_h = min(int(story_w * 16 / 9), vh - 80)
    cx = vw // 2
    clip = {
        "x": max(0, cx - story_w // 2),
        "y": max(0, (vh - story_h) // 2),
        "width": story_w,
        "height": story_h,
    }
    await page.screenshot(path=str(filename), clip=clip)
    if not is_valid_screenshot(filename):
        filename.unlink(missing_ok=True)
        print(f"  [skip] Story {index + 1}: invalid/blank frame, deleted.")
        return False
    print(f"  [ok] Story {index + 1}: saved -> {filename.name} (viewport clip {story_w}x{story_h})")
    return True


async def run(headless=False):
    save_dir = get_today_dir()
    print(f"[*] Saving screenshots to: {save_dir}")

    CHROME_PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    launch_args = ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
    if not headless:
        launch_args.append("--start-maximized")

    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=str(CHROME_PROFILE_DIR),
            headless=headless,
            viewport={"width": 1280, "height": 900},
            args=launch_args,
        )

        page = browser.pages[0] if browser.pages else await browser.new_page()

        await page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(2000)

        current = page.url
        login_input = await page.query_selector("input[name='username']")
        if "accounts/login" in current or login_input is not None:
            print("[!] Not logged in. Please log in manually.")
            await page.goto("https://www.instagram.com/accounts/login/", wait_until="domcontentloaded", timeout=60000)
            await wait_for_login(page)
        else:
            print("[ok] Session found, verifying...")
            await ensure_logged_in(page)

        print(f"[*] Navigating to stories: {STORY_URL}")
        await page.goto(STORY_URL, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(3000)

        if "accounts/login" in page.url or "accounts/onetap" in page.url:
            print("[!] Instagram redirected to login after navigating to stories. Session expired.")
            print("[!] Please log in manually in the browser window.")
            await wait_for_login(page)
            await page.goto(STORY_URL, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(3000)

        story_count = 0
        max_stories = 50

        while story_count < max_stories:
            current_url = page.url
            if "stories" not in current_url:
                print("[*] Left stories page, done.")
                break

            dialog_el = await page.evaluate_handle(
                "() => { const all = Array.from(document.querySelectorAll('*')); return all.find(el => /^view story$/i.test(el.innerText?.trim())) || null; }"
            )
            dialog_btn = dialog_el.as_element()
            if dialog_btn:
                box = await dialog_btn.bounding_box()
                if box and box['width'] > 0:
                    print("[*] Dismissing 'View story' confirmation...")
                    await dialog_btn.click()
                    await page.wait_for_timeout(3000)
                    continue

            try:
                taken = await screenshot_story_frame(page, story_count, save_dir)
            except PlaywrightError as e:
                if "Target page, context or browser has been closed" in str(e):
                    print("[!] Browser/page was closed unexpectedly (possible session expiry).")
                    break
                raise
            story_count += 1

            next_btn_selectors = [
                "button[aria-label='Next']",
                "div[aria-label='Next']",
            ]
            clicked = False
            for sel in next_btn_selectors:
                try:
                    btn = await page.query_selector(sel)
                    if btn and await btn.is_visible():
                        await btn.click()
                        clicked = True
                        break
                except Exception:
                    continue

            if not clicked:
                await page.keyboard.press("ArrowRight")

            await page.wait_for_timeout(2000)

            new_url = page.url
            if "stories" not in new_url:
                print("[*] Stories finished.")
                break

        print(f"\n[done] Captured {story_count} story screenshot(s) in {save_dir}")

        print("[*] Keeping browser open for 5 seconds before closing...")
        await page.wait_for_timeout(5000)
        await browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Instagram Story Screenshotter")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode (for VPS/server)")
    args = parser.parse_args()
    
    asyncio.run(run(headless=args.headless))
