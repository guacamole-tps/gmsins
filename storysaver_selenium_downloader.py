import time
import os
from datetime import datetime
from pathlib import Path
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, NoSuchElementException

TARGET_URL = "https://www.storysaver.net/en/download-instagram-story"
USERNAME = "gianmarcoschiarettiofficial"
PICS_DIR = Path(__file__).parent / "pics"
CHROME_PROFILE_DIR = Path(__file__).parent.parent / "chrome_profile"


def get_today_dir() -> Path:
    date_str = datetime.now().strftime("%Y-%m-%d")
    target = PICS_DIR / date_str
    target.mkdir(parents=True, exist_ok=True)
    return target


def dismiss_cookie_or_popup(driver):
    """Dismiss cookie banners and popups"""
    labels = ["Accept", "I Agree", "Agree", "Got it", "Allow all", "Consent"]
    
    for label in labels:
        try:
            button = driver.find_element(By.XPATH, f"//button[contains(., '{label}')]")
            button.click()
            time.sleep(0.5)
            return
        except NoSuchElementException:
            continue
    
    # Try generic cookie consent
    try:
        cookie_button = driver.find_element(By.XPATH, "//button[contains(@class, 'cookie') or contains(@id, 'cookie')]")
        cookie_button.click()
        time.sleep(0.5)
    except NoSuchElementException:
        pass


def fill_and_submit(driver):
    """Fill username and submit form"""
    # Try different input selectors
    input_selectors = [
        "//input[@type='text']",
        "//input[@name='username']",
        "//input[contains(@placeholder, 'username')]",
        "//input[contains(@placeholder, 'Instagram')]",
        "//input[not(@type='hidden')][not(@type='submit')][not(@type='button')]",
    ]
    
    input_element = None
    for selector in input_selectors:
        try:
            input_element = driver.find_element(By.XPATH, selector)
            if input_element.is_displayed() and input_element.is_enabled():
                break
        except NoSuchElementException:
            continue
    
    if not input_element:
        raise RuntimeError("Could not find the username input")
    
    # Clear and fill username
    input_element.clear()
    time.sleep(0.5)
    input_element.send_keys(USERNAME)
    time.sleep(1)
    
    # Try different button selectors
    button_selectors = [
        "//button[contains(., 'Download Now!')]",
        "//button[contains(., 'Download Now')]",
        "//button[@type='submit']",
        "//input[@type='submit']",
        "//button[contains(@class, 'submit')]",
        "//button[contains(@class, 'download')]",
    ]
    
    for selector in button_selectors:
        try:
            button = driver.find_element(By.XPATH, selector)
            if button.is_displayed() and button.is_enabled():
                button.click()
                return
        except NoSuchElementException:
            continue
    
    # Try pressing Enter as fallback
    input_element.send_keys(Keys.RETURN)


def wait_for_download_results(driver, timeout=180):
    """Wait for results to appear after Cloudflare verification"""
    wait = WebDriverWait(driver, timeout)
    
    try:
        # Wait for "Current stories" text
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Current stories')]")))
        print("[*] Found 'Current stories' section")
        
        # Wait for download buttons
        wait.until(EC.presence_of_element_located((By.XPATH, "//a[contains(., 'Save as Photo')]")))
        print("[*] Found 'Save as Photo' buttons")
        return True
    except TimeoutException:
        # Fallback: check for any download links
        try:
            download_links = driver.find_elements(By.XPATH, "//a[contains(@href, 'download') or contains(., 'Save')]")
            if download_links:
                print("[*] Found download links (fallback)")
                return True
        except:
            pass
        
        raise RuntimeError("Timed out waiting for download results")


def collect_photo_links(driver):
    """Collect all photo download links"""
    links = []
    seen = set()
    
    # Try different selectors for download links
    selectors = [
        "//a[contains(., 'Save as Photo')]",
        "//a[contains(@href, 'download')]",
        "//a[contains(@class, 'download')]",
        "//a[contains(@class, 'save')]",
    ]
    
    for selector in selectors:
        try:
            elements = driver.find_elements(By.XPATH, selector)
            for element in elements:
                href = element.get_attribute('href')
                if href and href not in seen:
                    seen.add(href)
                    links.append(href)
        except:
            continue
    
    return links


def download_photos(driver, save_dir, links):
    """Download photos by clicking links"""
    downloaded = 0
    
    for index, href in enumerate(links, start=1):
        try:
            # Open link in new tab
            driver.execute_script("window.open('', '_blank');")
            driver.switch_to.window(driver.window_handles[-1])
            driver.get(href)
            
            # Wait for download to start (image should load)
            time.sleep(3)
            
            # Try to find and click download button if present
            try:
                download_btn = driver.find_element(By.XPATH, "//button[contains(., 'Download') or contains(., 'Save')]")
                download_btn.click()
                time.sleep(2)
            except:
                pass
            
            # Get the image URL and download it directly
            try:
                img = driver.find_element(By.TAG_NAME, "img")
                img_url = img.get_attribute('src')
                if img_url:
                    import requests
                    response = requests.get(img_url)
                    if response.status_code == 200:
                        filename = save_dir / f"{index:03d}.jpg"
                        with open(filename, 'wb') as f:
                            f.write(response.content)
                        print(f"  [ok] Saved -> {filename.name}")
                        downloaded += 1
            except:
                pass
            
            # Close tab and return to main
            driver.close()
            driver.switch_to.window(driver.window_handles[0])
            
        except Exception as e:
            print(f"  [warn] Failed to download item {index}: {e}")
            # Make sure we're back to main window
            if len(driver.window_handles) > 1:
                driver.close()
                driver.switch_to.window(driver.window_handles[0])
    
    return downloaded


def main():
    save_dir = get_today_dir()
    print(f"[*] Saving downloads to: {save_dir}")
    
    # Setup Chrome options
    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-web-security")
    options.add_argument("--allow-running-insecure-content")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--ignore-ssl-errors")
    options.add_argument("--ignore-certificate-errors-spki-list")
    
    # Use existing profile if available
    if CHROME_PROFILE_DIR.exists():
        options.add_argument(f"--user-data-dir={CHROME_PROFILE_DIR}")
    
    try:
        # Initialize undetected Chrome driver
        print("[*] Starting browser...")
        driver = uc.Chrome(options=options, version_main=None)
        
        # Navigate to target
        print(f"[*] Navigating to: {TARGET_URL}")
        driver.get(TARGET_URL)
        time.sleep(3)
        
        # Dismiss popups
        dismiss_cookie_or_popup(driver)
        
        # Fill and submit
        print(f"[*] Submitting username: {USERNAME}")
        fill_and_submit(driver)
        
        # Wait for results
        print("[*] Waiting for Cloudflare verification and results...")
        wait_for_download_results(driver)
        time.sleep(2)
        
        # Collect and download
        links = collect_photo_links(driver)
        if not links:
            raise RuntimeError("No download links found")
        
        print(f"[*] Found {len(links)} photo link(s)")
        downloaded = download_photos(driver, save_dir, links)
        
        print(f"[done] Downloaded {downloaded} photo(s) to {save_dir}")
        
        # Keep browser open for inspection
        print("[*] Keeping browser open for 30 seconds...")
        time.sleep(30)
        
    except Exception as e:
        print(f"[error] {e}")
        print("[*] Keeping browser open for 60 seconds for manual inspection...")
        time.sleep(60)
    finally:
        try:
            driver.quit()
        except:
            pass


if __name__ == "__main__":
    main()
