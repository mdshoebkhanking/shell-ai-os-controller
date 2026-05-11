#!/usr/bin/env python3
"""
Real WhatsApp Web Integration using Browser Automation
Captures actual QR code from web.whatsapp.com
"""

import os
import time
import base64
from io import BytesIO
from PIL import Image
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import logging
try:
    from shell_safe_executor import god_tier_tool as function_tool
except ImportError:
    def function_tool(func): return func

logger = logging.getLogger("whatsapp_web_real")

class WhatsAppWebReal:
    """Real WhatsApp Web integration using browser automation"""
    
    def __init__(self):
        self.driver = None
        self.qr_image = None
        self.connected = False
    
    def start_session(self, headless=False):
        """Start WhatsApp Web session and get QR code"""
        try:
            # Chrome options
            chrome_options = Options()
            if headless:
                chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            
            # User data directory for persistent session
            user_data_dir = os.path.expanduser("~/.shell_whatsapp_chrome")
            chrome_options.add_argument(f"--user-data-dir={user_data_dir}")
            
            logger.info("🚀 Starting Chrome for WhatsApp Web...")
            self.driver = webdriver.Chrome(options=chrome_options)
            
            # Open WhatsApp Web
            self.driver.get("https://web.whatsapp.com")
            logger.info("📱 Opened WhatsApp Web")
            
            # Wait for QR code or main page
            time.sleep(3)
            
            # Check if already logged in
            try:
                # If we see the main chat interface, we're logged in
                WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="chat-list"]'))
                )
                logger.info("✅ Already logged in!")
                self.connected = True
                return True, None  # No QR needed
            except Exception:
                # Not logged in, need QR
                pass
            
            # Capture QR code
            qr_element = self.wait_for_qr()
            if qr_element:
                self.qr_image = self.capture_qr_image(qr_element)
                logger.info("📸 QR Code captured!")
                return True, self.qr_image
            else:
                return False, "❌ QR code not found"
                
        except Exception as e:
            logger.error(f"WhatsApp Web error: {e}")
            return False, f"❌ Error: {str(e)}"
    
    def wait_for_qr(self, timeout=30):
        """Wait for QR code element to appear"""
        try:
            # WhatsApp Web QR code canvas
            qr_element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'canvas[aria-label="Scan this QR code to link a device!"]'))
            )
            return qr_element
        except Exception as e:
            logger.error(f"QR code not found: {e}")
            return None
    
    def capture_qr_image(self, qr_element):
        """Capture QR code as PIL Image"""
        try:
            # Get QR code canvas as base64 PNG
            qr_base64 = self.driver.execute_script(
                "return arguments[0].toDataURL('image/png').substring(21);",
                qr_element
            )
            
            # Decode base64 to image
            qr_bytes = base64.b64decode(qr_base64)
            qr_image = Image.open(BytesIO(qr_bytes))
            
            return qr_image
        except Exception as e:
            logger.error(f"Failed to capture QR: {e}")
            return None
    
    def wait_for_login(self, timeout=60):
        """Wait for user to scan QR and login"""
        try:
            # Wait for main chat interface
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="chat-list"]'))
            )
            logger.info("✅ WhatsApp Web connected!")
            self.connected = True
            return True
        except Exception as e:
            logger.error(f"Login timeout: {e}")
            return False
    
    def get_new_messages(self):
        """Get unread messages from WhatsApp Web"""
        if not self.connected or not self.driver:
            return []
        
        try:
            # Find unread chats
            unread_chats = self.driver.find_elements(
                By.CSS_SELECTOR, 
                '[data-testid="cell-frame-container"] span[aria-label*="unread"]'
            )
            
            messages = []
            for chat in unread_chats[:5]:  # Limit to 5 most recent
                try:
                    # Click chat to open
                    chat.click()
                    time.sleep(1)
                    
                    # Get chat name
                    name_elem = self.driver.find_element(By.CSS_SELECTOR, '[data-testid="conversation-header"] span[title]')
                    sender = name_elem.get_attribute('title')
                    
                    # Get last message
                    msg_elems = self.driver.find_elements(By.CSS_SELECTOR, '[data-testid="msg-container"] span.selectable-text')
                    if msg_elems:
                        last_msg = msg_elems[-1].text
                        messages.append({
                            'from': sender,
                            'body': last_msg,
                            'timestamp': time.time()
                        })
                except Exception as e:
                    logger.error(f"Error reading message: {e}")
                    continue
            
            return messages
        except Exception as e:
            logger.error(f"Failed to get messages: {e}")
            return []
    
    def send_message(self, contact_name, message):
        """Send message to a contact"""
        if not self.connected or not self.driver:
            return False, "❌ Not connected"
        
        try:
            # Search for contact
            search_box = self.driver.find_element(By.CSS_SELECTOR, '[data-testid="chat-list-search"]')
            search_box.click()
            search_box.send_keys(contact_name)
            time.sleep(2)
            
            # Click first result
            first_result = self.driver.find_element(By.CSS_SELECTOR, '[data-testid="cell-frame-container"]')
            first_result.click()
            time.sleep(1)
            
            # Type message
            msg_box = self.driver.find_element(By.CSS_SELECTOR, '[data-testid="conversation-compose-box-input"]')
            msg_box.send_keys(message)
            
            # Send
            send_btn = self.driver.find_element(By.CSS_SELECTOR, '[data-testid="send"]')
            send_btn.click()
            
            logger.info(f"✅ Message sent to {contact_name}")
            return True, f"✅ Message sent to {contact_name}"
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False, f"❌ Error: {str(e)}"
    
    def close(self):
        """Close browser session"""
        if self.driver:
            self.driver.quit()
            self.driver = None
            self.connected = False

import asyncio

# Global instance
whatsapp_web_real = WhatsAppWebReal()

# Agent Tool Wrappers

@function_tool
async def link_whatsapp_device() -> str:
    """
    🔗 Link Shell to your WhatsApp (Web)
    
    1. Launches a browser window with WhatsApp Web.
    2. Shows a QR Code on your screen.
    3. Scan it with your phone (WhatsApp -> Linked Devices).
    4. Shell will then have DIRECT access to your chats!
    """
    try:
        # Start visible session (Run in thread to avoid blocking loop)
        success, result = await asyncio.to_thread(whatsapp_web_real.start_session, headless=False)
        
        if success:
            # If result is None, it means already logged in
            if not result or result is True:
                 return "✅ WhatsApp successfully linked & connected! You can now ask me to check or send messages."
            
            # If result is an image (QR), we return instructions
            return "📸 QR Code is on your screen! Please scan it with your phone (WhatsApp -> Menu -> Linked devices). Once scanned, tell me 'I scanned it'."
        else:
            return f"❌ Failed to launch WhatsApp Web: {result}"
    except Exception as e:
        logger.error(f"Link error: {e}")
        return f"❌ Error: {str(e)}"

@function_tool
async def whatsapp_web_send(contact: str, message: str) -> str:
    """
    📤 Send WhatsApp Message (via Web Integration)
    
    Args:
        contact: Name of the contact (must be exact match).
        message: The message to send.
    """
    # Run in thread
    success, msg = await asyncio.to_thread(whatsapp_web_real.send_message, contact, message)
    return msg

@function_tool
async def whatsapp_web_check() -> str:
    """
    📥 Check for new unread WhatsApp messages (via Web Integration)
    """
    # Run in thread
    msgs = await asyncio.to_thread(whatsapp_web_real.get_new_messages)
    if not msgs:
        return (
            "📭 No new unread messages found.\n"
            "Koi naya message nahi mila — sab padh liya!"
        )

    import datetime
    total = len(msgs)
    response_lines = [
        f"📨 Found {total} new message{'s' if total > 1 else ''} / {total} naye messages mile:",
        f"{'─'*45}"
    ]

    for idx, m in enumerate(msgs, 1):
        # Enhanced timestamp formatting
        time_str = "⏰ N/A"
        if 'timestamp' in m:
            dt = datetime.datetime.fromtimestamp(m['timestamp'])
            time_str = dt.strftime("📅 %Y-%m-%d | 🕐 %H:%M:%S")

        response_lines.append(
            f"\n  [{idx}/{total}] 👤 {m['from']}\n"
            f"    {time_str}\n"
            f"    💬 {m['body']}"
        )

    response_lines.append(f"\n{'─'*45}")
    response_lines.append(f"📊 Total: {total} unread messages")

    return "\n".join(response_lines)


@function_tool
async def whatsapp_web_status_tool() -> str:
    """
    🌐 WhatsApp Web Connection Status
    Shows connection state, browser session, profile directory, and last activity.
    WhatsApp Web ka full status check — connected hai ya nahi, sab batayega!
    """
    import datetime

    profile_dir = os.path.expanduser("~/.shell_whatsapp_chrome")
    profile_exists = os.path.exists(profile_dir)

    # Check connection status
    is_connected = whatsapp_web_real.connected
    has_driver = whatsapp_web_real.driver is not None

    # Browser session active check
    browser_active = False
    if has_driver:
        try:
            # If we can get the title, the browser is still alive
            _ = whatsapp_web_real.driver.title
            browser_active = True
        except Exception:
            browser_active = False

    # Last activity from profile directory
    last_activity = "N/A"
    if profile_exists:
        try:
            mtime = os.path.getmtime(profile_dir)
            dt = datetime.datetime.fromtimestamp(mtime)
            last_activity = dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception as _e:
            logger.debug("ignored Exception: %s", _e)

    conn_icon = "✅" if is_connected else "❌"
    browser_icon = "✅" if browser_active else "❌"
    profile_icon = "✅" if profile_exists else "❌"

    return (
        f"🌐 WhatsApp Web Status / वेब स्थिति:\n"
        f"{'='*45}\n"
        f"{conn_icon} Connection: {'CONNECTED — जुड़ा हुआ है' if is_connected else 'DISCONNECTED — जुड़ा नहीं है'}\n"
        f"{browser_icon} Browser Session: {'ACTIVE — चालू है' if browser_active else 'INACTIVE — बंद है'}\n"
        f"{profile_icon} Profile Directory: {profile_dir}\n"
        f"   {'(exists)' if profile_exists else '(not found — pehle link karo!)'}\n"
        f"🕐 Last Activity: {last_activity}\n"
        f"{'='*45}\n"
        f"{'Sab set hai — WhatsApp Web ready!' if is_connected and browser_active else 'Pehle link_whatsapp_device se connect karo!'}"
    )
