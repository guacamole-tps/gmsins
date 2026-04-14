import webbrowser
from datetime import datetime
from pathlib import Path

TARGET_URL = "https://www.storysaver.net/en/download-instagram-story"
USERNAME = "gianmarcoschiarettiofficial"
PICS_DIR = Path(__file__).parent / "pics"


def get_today_dir() -> Path:
    date_str = datetime.now().strftime("%Y-%m-%d")
    target = PICS_DIR / date_str
    target.mkdir(parents=True, exist_ok=True)
    return target


def main():
    save_dir = get_today_dir()
    print(f"[*] Today's download directory: {save_dir}")
    print(f"[*] Opening browser to: {TARGET_URL}")
    print(f"[*] Username to enter: {USERNAME}")
    print("\n" + "="*60)
    print("MANUAL INSTRUCTIONS:")
    print("1. Browser will open the storysaver.net page")
    print("2. Complete Cloudflare verification if prompted")
    print("3. Enter username:", USERNAME)
    print("4. Click 'Download Now!' button")
    print("5. Wait for stories to load")
    print("6. Right-click each 'Save as Photo' link and save to:")
    print(f"   {save_dir}")
    print("="*60)
    print("\n[*] Opening browser...")
    
    webbrowser.open(TARGET_URL)
    
    input("\nPress Enter after you finish downloading...")


if __name__ == "__main__":
    main()
