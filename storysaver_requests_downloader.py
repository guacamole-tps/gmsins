import re
import time
import urllib3
from datetime import datetime
from pathlib import Path
import cloudscraper
from bs4 import BeautifulSoup
import requests

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TARGET_URL = "https://www.storysaver.net/en/download-instagram-story"
USERNAME = "gianmarcoschiarettiofficial"
PICS_DIR = Path(__file__).parent / "pics"


def get_today_dir() -> Path:
    date_str = datetime.now().strftime("%Y-%m-%d")
    target = PICS_DIR / date_str
    target.mkdir(parents=True, exist_ok=True)
    return target


def extract_csrf_token(soup):
    """Extract CSRF token from form"""
    csrf_input = soup.find('input', {'name': '_token'})
    if csrf_input:
        return csrf_input.get('value')
    
    # Try other common CSRF token names
    for name in ['csrf_token', 'authenticity_token', '_csrf', 'token']:
        token_input = soup.find('input', {'name': name})
        if token_input:
            return token_input.get('value')
    
    return None


def extract_session_cookies(session):
    """Extract session cookies for persistence"""
    cookies = {}
    for cookie in session.cookies:
        cookies[cookie.name] = cookie.value
    return cookies


def download_image(url, save_path):
    """Download image from URL"""
    try:
        response = requests.get(url, timeout=30, verify=False)
        response.raise_for_status()
        
        with open(save_path, 'wb') as f:
            f.write(response.content)
        return True
    except Exception as e:
        print(f"  [warn] Failed to download {url}: {e}")
        return False


def main():
    save_dir = get_today_dir()
    print(f"[*] Saving downloads to: {save_dir}")
    
    # Create cloudscraper session with custom SSL context
    print("[*] Initializing cloudscraper session...")
    
    # Create unverified SSL context
    import ssl
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True
        },
        ssl_context=ssl_context
    )
    
    try:
        # Get initial page
        print(f"[*] Fetching: {TARGET_URL}")
        response = scraper.get(TARGET_URL)
        response.raise_for_status()
        
        # Parse the page
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find the form
        form = soup.find('form')
        if not form:
            # Try to find form by method
            forms = soup.find_all('form', method=lambda x: x and x.lower() == 'post')
            if forms:
                form = forms[0]
        
        if not form:
            raise RuntimeError("Could not find the submission form")
        
        # Extract form action and CSRF token
        action = form.get('action', TARGET_URL)
        if not action.startswith('http'):
            action = f"https://www.storysaver.net{action}"
        
        csrf_token = extract_csrf_token(soup)
        
        # Prepare form data
        form_data = {}
        
        # Find username input
        username_input = form.find('input', {'type': 'text'}) or form.find('input', {'name': 'username'})
        if username_input:
            input_name = username_input.get('name', 'username')
            form_data[input_name] = USERNAME
        else:
            form_data['username'] = USERNAME
        
        # Add CSRF token if found
        if csrf_token:
            form_data['_token'] = csrf_token
        
        print(f"[*] Submitting form with username: {USERNAME}")
        
        # Submit form
        submit_response = scraper.post(action, data=form_data)
        submit_response.raise_for_status()
        
        # Parse results page
        result_soup = BeautifulSoup(submit_response.text, 'html.parser')
        
        # Look for story links
        story_links = []
        
        # Try different selectors for story links
        selectors = [
            'a[href*="download"]',
            'a:contains("Save as Photo")',
            'a:contains("Download")',
            '.story-item a',
            '.download-link a',
            'a[href*=".jpg"]',
            'a[href*=".png"]',
        ]
        
        for selector in selectors:
            links = result_soup.select(selector)
            for link in links:
                href = link.get('href')
                if href and href not in story_links:
                    # Make URL absolute if needed
                    if href.startswith('/'):
                        href = f"https://www.storysaver.net{href}"
                    elif not href.startswith('http'):
                        continue
                    
                    story_links.append(href)
        
        # Also try to find image sources directly
        images = result_soup.find_all('img', src=True)
        for img in images:
            src = img.get('src')
            if src and ('story' in src.lower() or 'download' in src.lower()):
                if src.startswith('/'):
                    src = f"https://www.storysaver.net{src}"
                elif not src.startswith('http'):
                    continue
                
                if src not in story_links:
                    story_links.append(src)
        
        if not story_links:
            # Try to find any links in the page that might be stories
            all_links = result_soup.find_all('a', href=True)
            for link in all_links:
                href = link.get('href')
                text = link.get_text().strip().lower()
                
                if ('save' in text or 'download' in text or 'photo' in text) and href not in story_links:
                    if href.startswith('/'):
                        href = f"https://www.storysaver.net{href}"
                    elif not href.startswith('http'):
                        continue
                    
                    story_links.append(href)
        
        if not story_links:
            print("[!] No story links found. The site structure might have changed.")
            print("[*] Saving response HTML for inspection...")
            debug_file = save_dir / "debug_response.html"
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(submit_response.text)
            print(f"[*] Debug HTML saved to: {debug_file}")
            return
        
        print(f"[*] Found {len(story_links)} story link(s)")
        
        # Download stories
        downloaded = 0
        for index, link in enumerate(story_links, start=1):
            print(f"  [*] Downloading story {index}/{len(story_links)}")
            
            # Determine filename
            if link.endswith('.jpg') or link.endswith('.png'):
                filename = f"{index:03d}{Path(link).suffix}"
            else:
                filename = f"{index:03d}.jpg"
            
            save_path = save_dir / filename
            
            if download_image(link, save_path):
                print(f"  [ok] Saved -> {filename}")
                downloaded += 1
            else:
                print(f"  [fail] Could not download {link}")
            
            # Small delay between downloads
            time.sleep(1)
        
        print(f"[done] Downloaded {downloaded}/{len(story_links)} stories to {save_dir}")
        
    except Exception as e:
        print(f"[error] {e}")
        
        # Save debug info
        try:
            debug_file = save_dir / "debug_error.html"
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(response.text)
            print(f"[*] Debug HTML saved to: {debug_file}")
        except:
            pass


if __name__ == "__main__":
    main()
