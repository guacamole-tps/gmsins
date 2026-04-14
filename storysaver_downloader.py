import asyncio
from datetime import datetime
from pathlib import Path

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

TARGET_URL = "https://www.storysaver.net/en/download-instagram-story"
USERNAME = "gianmarcoschiarettiofficial"
PICS_DIR = Path(__file__).parent / "pics"
CHROME_PROFILE_DIR = Path(__file__).parent.parent / "chrome_profile"


def get_today_dir() -> Path:
    date_str = datetime.now().strftime("%Y-%m-%d")
    target = PICS_DIR / date_str
    target.mkdir(parents=True, exist_ok=True)
    return target


async def wait_for_download_results(page):
    current_stories = page.get_by_text("Current stories", exact=False)
    save_buttons = page.get_by_role("link", name="Save as Photo")

    for i in range(180):
        try:
            if await current_stories.count() > 0 and await save_buttons.count() > 0:
                return
            await page.wait_for_timeout(1000)
        except Exception as e:
            print(f"  [warn] Waiting interrupted at iteration {i+1}: {e}")
            break

    # Fallback: wait for any 'Save as Photo' link or similar download button
    try:
        fallback = page.locator("a").filter(has_text="Save as Photo")
        if await fallback.count() > 0:
            print("[*] Fallback: found 'Save as Photo' links")
            return
    except Exception:
        pass

    raise RuntimeError("Timed out waiting for 'Current stories' and 'Save as Photo' buttons.")


async def fill_and_submit(page):
    input_selectors = [
        "input[type='text']",
        "input[name='username']",
        "input[placeholder*='username' i]",
        "input[placeholder*='Instagram' i]",
        "input",
    ]

    input_locator = None
    for selector in input_selectors:
        locator = page.locator(selector).first
        try:
            await locator.wait_for(state="visible", timeout=5000)
            input_locator = locator
            break
        except PlaywrightTimeoutError:
            continue

    if input_locator is None:
        raise RuntimeError("Could not find the username input on storysaver.net.")

    await input_locator.click()
    await input_locator.fill(USERNAME)

    button_candidates = [
        page.get_by_role("button", name="Download Now!"),
        page.get_by_role("button", name="Download Now"),
        page.get_by_text("Download Now!", exact=False),
        page.get_by_text("Download Now", exact=False),
        page.locator("button[type='submit']").first,
        page.locator("input[type='submit']").first,
    ]

    for button in button_candidates:
        try:
            await button.click(timeout=5000)
            return
        except Exception:
            continue

    raise RuntimeError("Could not click the 'Download Now!' button.")


async def dismiss_cookie_or_popup(page):
    labels = [
        "Accept",
        "I Agree",
        "Agree",
        "Got it",
        "Allow all",
    ]

    for label in labels:
        try:
            button = page.get_by_role("button", name=label).first
            if await button.count() > 0:
                await button.click(timeout=1000)
                await page.wait_for_timeout(500)
                return
        except Exception:
            continue


async def collect_photo_links(page):
    links = []
    seen = set()

    button_candidates = page.get_by_role("link", name="Save as Photo")
    count = await button_candidates.count()
    for index in range(count):
        locator = button_candidates.nth(index)
        href = await locator.get_attribute("href")
        if href and href not in seen:
            seen.add(href)
            links.append(href)

    if links:
        return links

    hrefs = await page.locator("a[href]").evaluate_all(
        """
        (elements) => elements
            .filter((el) => /save as photo/i.test((el.innerText || '').trim()))
            .map((el) => el.href)
            .filter(Boolean)
        """
    )
    for href in hrefs:
        if href not in seen:
            seen.add(href)
            links.append(href)

    return links


async def download_photo(page, href: str, save_dir: Path, index: int):
    filename = save_dir / f"{index:03d}.jpg"

    async with page.expect_download(timeout=120000) as download_info:
        await page.evaluate("url => window.open(url, '_blank')", href)
    download = await download_info.value
    suggested = download.suggested_filename
    if suggested:
        filename = save_dir / f"{index:03d}{Path(suggested).suffix or '.jpg'}"
    await download.save_as(str(filename))
    print(f"  [ok] Saved -> {filename.name}")


async def run():
    save_dir = get_today_dir()
    print(f"[*] Saving downloads to: {save_dir}")

    CHROME_PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=str(CHROME_PROFILE_DIR),
            headless=False,
            accept_downloads=True,
            viewport={"width": 1400, "height": 1000},
            args=[
                "--start-maximized",
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
                "--disable-features=VizDisplayCompositor"
            ],
        )

        page = browser.pages[0] if browser.pages else await browser.new_page()
        
        # Apply stealth to bypass Cloudflare
        stealth_obj = Stealth()
        await stealth_obj.apply_stealth_async(page)
        
        try:
            await page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=120000)
            await page.wait_for_timeout(3000)
            await dismiss_cookie_or_popup(page)

            print(f"[*] Submitting username: {USERNAME}")
            await fill_and_submit(page)

            print("[*] Waiting for Cloudflare verification and story results...")
            await wait_for_download_results(page)
            await page.wait_for_timeout(1500)

            links = await collect_photo_links(page)
            if not links:
                raise RuntimeError("No 'Save as Photo' links found after results loaded.")

            print(f"[*] Found {len(links)} photo download link(s)")
            for index, href in enumerate(links, start=1):
                try:
                    await download_photo(page, href, save_dir, index)
                except Exception as exc:
                    print(f"  [warn] Failed to download item {index}: {exc}")

            print(f"[done] Downloads saved in {save_dir}")
            print("[*] Keeping browser open for 5 seconds before closing...")
            await page.wait_for_timeout(5000)
        except Exception as e:
            print(f"[error] Main process failed: {e}")
            print("[*] Keeping browser open for 30 seconds for manual inspection...")
            await page.wait_for_timeout(30000)
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(run())
