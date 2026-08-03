import time
import os
import sys
from pathlib import Path
import mss

# Add path to import local modules
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shell_email_web import gmail_web_mailer

def main():
    print("Starting Gmail Web Mailer session (headless=False)...")
    ok, message = gmail_web_mailer.start_session(headless=False)
    print(f"Start session result: ok={ok}, message={message}")
    
    if not ok:
        print("Failed to start session!")
        sys.exit(1)
        
    print("Waiting 15 seconds for the Google Login page to fully load...")
    gmail_web_mailer.driver.get("https://accounts.google.com/ServiceLogin?service=mail")
    time.sleep(15)
    
    screenshot_path = "C:/Users/Administrator/.gemini/antigravity-ide/brain/0a274b89-dcc8-4ed8-9b61-0e7dc25a0e35/gmail_secure_bypass.png"
    print(f"Capturing Chrome page screenshot to {screenshot_path}...")
    try:
        gmail_web_mailer.driver.save_screenshot(screenshot_path)
        print("Chrome page screenshot captured successfully!")
    except Exception as e:
        print(f"Error capturing Chrome page screenshot: {e}")
        
    print("Closing Gmail Web Mailer session...")
    gmail_web_mailer.close()
    print("Done!")

if __name__ == "__main__":
    main()
