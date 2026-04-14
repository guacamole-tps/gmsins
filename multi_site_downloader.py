import time
from datetime import datetime
from pathlib import Path
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

USERNAME = "gianmarcoschiarettiofficial"
PICS_DIR = Path(__file__).parent / "pics"


def get_today_dir() -> Path:
    date_str = datetime.now().strftime("%Y-%m-%d")
    target = PICS_DIR / date_str
    target.mkdir(parents=True, exist_ok=True)
    return target


def try_site_storiesig():
    """Try storiesig.net"""
    try:
        options = uc.ChromeOptions()
        options.add_argument("--start-maximized")
        options.add_argument("--ignore-certificate-errors")
        
        driver = uc.Chrome(options=options)
        
        print("[*] Trying storiesig.net...")
        driver.get("https://storiesig.net/")
        time.sleep(3)
        
        # Find input and submit
        input_elem = driver.find_element(By.NAME, "username")
        input_elem.send_keys(USERNAME)
        input_elem.send_keys(Keys.RETURN)
        
        # Wait for results
        time.sleep(10)
        
        # Look for download links
        links = driver.find_elements(By.XPATH, "//a[contains(@href, 'download')]")
        print(f"[*] Found {len(links)} download links")
        
        return driver, links
        
    except Exception as e:
        print(f"[!] storiesig.net failed: {e}")
        return None, []


def try_site_instanavigation():
    """Try instanavigation.com"""
    try:
        options = uc.ChromeOptions()
        options.add_argument("--start-maximized")
        options.add_argument("--ignore-certificate-errors")
        
        driver = uc.Chrome(options=options)
        
        print("[*] Trying instanavigation.com...")
        driver.get("https://instanavigation.com/")
        time.sleep(3)
        
        # Find input and submit
        input_elem = driver.find_element(By.XPATH, "//input[@placeholder='Enter Instagram username']")
        input_elem.send_keys(USERNAME)
        input_elem.send_keys(Keys.RETURN)
        
        # Wait for results
        time.sleep(10)
        
        # Look for download links
        links = driver.find_elements(By.XPATH, "//a[contains(@href, 'download')]")
        print(f"[*] Found {len(links)} download links")
        
        return driver, links
        
    except Exception as e:
        print(f"[!] instanavigation.com failed: {e}")
        return None, []


def try_site_dumpinstagram():
    """Try dumpinstagram.com"""
    try:
        options = uc.ChromeOptions()
        options.add_argument("--start-maximized")
        options.add_argument("--ignore-certificate-errors")
        
        driver = uc.Chrome(options=options)
        
        print("[*] Trying dumpinstagram.com...")
        driver.get("https://dumpinstagram.com/")
        time.sleep(3)
        
        # Find input and submit
        input_elem = driver.find_element(By.NAME, "username")
        input_elem.send_keys(USERNAME)
        input_elem.send_keys(Keys.RETURN)
        
        # Wait for results
        time.sleep(10)
        
        # Look for download links
        links = driver.find_elements(By.XPATH, "//a[contains(@href, 'download')]")
        print(f"[*] Found {len(links)} download links")
        
        return driver, links
        
    except Exception as e:
        print(f"[!] dumpinstagram.com failed: {e}")
        return None, []


def main():
    save_dir = get_today_dir()
    print(f"[*] Saving downloads to: {save_dir}")
    print("\n[*] Trying multiple Instagram story download sites...")
    
    sites = [
        try_site_storiesig,
        try_site_instanavigation,
        try_site_dumpinstagram,
    ]
    
    for site_func in sites:
        driver, links = site_func()
        if driver and links:
            print(f"\n[SUCCESS] Found {len(links)} stories!")
            print("[*] Browser will stay open for 60 seconds for manual download...")
            print(f"[*] Download to: {save_dir}")
            time.sleep(60)
            driver.quit()
            return
        elif driver:
            driver.quit()
    
    print("\n[!] All sites failed. You may need to:")
    print("1. Complete manual Cloudflare verification")
    print("2. Try a different VPN/proxy")
    print("3. Use the storysaver_helper.py script for manual download")


if __name__ == "__main__":
    main()
