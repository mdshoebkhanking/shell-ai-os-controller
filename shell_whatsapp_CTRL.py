
import webbrowser
import asyncio
import logging
from shell_safe_executor import god_tier_tool as function_tool

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("WHATSAPP_CTRL")

# Global variable to track if WhatsApp is already running (shared state)
# Note: shell_whatsapp_ULTRA.py has its own copy — they operate independently
_whatsapp_already_running = False
_whatsapp_state_lock = __import__('threading').Lock()

# Message tracking stats
_messages_sent_count = 0
_last_recipient = None
_last_send_time = None
_last_send_mode = None

async def launch_whatsapp() -> tuple[bool, str]:
    """
    Launches WhatsApp Desktop app using multiple methods.
    Returns: (success: bool, mode: str)
    """
    import subprocess
    import os
    global _whatsapp_already_running
    
    logger.info("🚀 Attempting to launch WhatsApp...")
    
    # Check if WhatsApp is already running
    try:
        import psutil
        for proc in psutil.process_iter(['name']):
            try:
                if proc.info['name'] and 'whatsapp' in proc.info['name'].lower():
                    logger.info("✅ WhatsApp already running!")
                    with _whatsapp_state_lock:
                        _whatsapp_already_running = True
                    await asyncio.sleep(1.0)  # Short wait
                    return True, "app"
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception as e:
        logger.warning(f"Process check failed: {e}")
    common_paths = [
        os.path.expandvars(r"%LOCALAPPDATA%\WhatsApp\WhatsApp.exe"),
        os.path.expandvars(r"%PROGRAMFILES%\WhatsApp\WhatsApp.exe"),
        os.path.expandvars(r"%PROGRAMFILES(X86)%\WhatsApp\WhatsApp.exe"),
    ]
    
    for path in common_paths:
        if os.path.exists(path):
            try:
                logger.info(f"✅ Found WhatsApp at: {path}")
                subprocess.Popen([path])
                _whatsapp_already_running = False  # First launch
                await asyncio.sleep(5.0)  # Longer wait for first launch
                return True, "app"
            except Exception as e:
                logger.warning(f"Failed to launch from {path}: {e}")
    
    # Method 2: Try Windows Start menu
    try:
        logger.info("🔍 Trying Windows Start menu...")
        subprocess.Popen(["cmd", "/c", "start", "whatsapp:"])
        _whatsapp_already_running = False  # First launch
        await asyncio.sleep(5.0)  # Longer wait for first launch
        return True, "app"
    except Exception as e:
        logger.warning(f"Start menu launch failed: {e}")
    
    # Method 3: Fallback to Web
    logger.info("🌐 Falling back to WhatsApp Web...")
    return False, "web"

@function_tool
async def send_whatsapp_message(recipient: str, message: str) -> str:
    """
    Sends a WhatsApp message via WhatsApp Web using browser automation.
    Requires user to be already logged into web.whatsapp.com.

    Args:
        recipient (str): The name/contact to search for (e.g., "Raj", "Mummy").
        message (str): The final message text to send.
    """
    # Input validation
    if not recipient or not recipient.strip():
        return "❌ Recipient name is required."
    if not message or not message.strip():
        return "❌ Message text is required."
    recipient = recipient.strip()
    message = message.strip()

    logger.info(f"🔥 WHATSAPP TOOL EXECUTING: {recipient} -> {message[:50]}...")
    
    try:
        import pyautogui
        import time
        import asyncio
        import webbrowser
        import pyperclip
        import subprocess
        
        from shell_window_CTRL import focus_window
        from vision_engine import vision_engine

        # 1. Launch WhatsApp
        mode = "web"
        found_app = False
        
        logger.info("📱 Launching WhatsApp...")
        found_app, mode = await launch_whatsapp()
        
        if found_app:
            logger.info("✅ WhatsApp Desktop App launched!")
            # Adaptive wait time
            wait_time = 1.0 if _whatsapp_already_running else 3.0
            await asyncio.sleep(wait_time)
            await focus_window("whatsapp")
            await asyncio.sleep(0.5)
        else:
            logger.info("🌍 Opening WhatsApp Web...")
            webbrowser.open("https://web.whatsapp.com")
            await asyncio.sleep(4.0)
            
            for browser in ["chrome", "google chrome", "edge", "firefox"]:
                if await focus_window(browser):
                    break
            await asyncio.sleep(1.0)

        # 2. ENSURE FOCUS
        logger.info("🎯 Ensuring window focus...")
        screen_width, screen_height = pyautogui.size()
        center_x, center_y = screen_width // 2, screen_height // 2
        
        pyautogui.click(center_x, center_y)
        focus_wait = 1.0 if _whatsapp_already_running else 2.0
        await asyncio.sleep(focus_wait)
        
        # 3. SEARCH - CTRL+F METHOD (WhatsApp Desktop)
        logger.info(f"🔍 Searching contact: {recipient}")
        
        # Adaptive timing
        search_wait = 2.0 if _whatsapp_already_running else 3.0
        result_wait = 3.0 if _whatsapp_already_running else 6.0
        chat_wait = 2.0 if _whatsapp_already_running else 4.0
        
        search_success = False
        for attempt in range(3):
            try:
                logger.info(f"Attempt {attempt + 1}/3...")
                
                # STEP 1: Open search with Ctrl+F
                logger.info("Opening search with Ctrl+F...")
                pyautogui.hotkey('ctrl', 'f')
                await asyncio.sleep(search_wait)
                
                # STEP 2: Clear everything
                logger.info("Clearing search box...")
                for _ in range(3):
                    pyautogui.hotkey('ctrl', 'a')
                    await asyncio.sleep(0.1)
                    pyautogui.press('delete')
                    await asyncio.sleep(0.1)
                
                await asyncio.sleep(0.5)
                
                # STEP 3: Type contact name
                logger.info(f"Typing: {recipient}")
                pyperclip.copy(recipient)
                await asyncio.sleep(0.3)
                pyautogui.hotkey('ctrl', 'v')
                
                # STEP 4: Wait for results (adaptive)
                logger.info("Waiting for search results...")
                await asyncio.sleep(result_wait)
                
                # STEP 5: Select first result
                logger.info("Selecting first result...")
                pyautogui.press('down')
                await asyncio.sleep(0.5)
                pyautogui.press('enter')
                
                # STEP 6: Wait for chat (adaptive)
                logger.info("Waiting for chat...")
                await asyncio.sleep(chat_wait)
                
                search_success = True
                logger.info("✅ Chat opened!")
                break
                
            except Exception as e:
                logger.warning(f"Attempt {attempt+1} failed: {e}")
                await asyncio.sleep(1.0)
        
        if not search_success:
            return "❌ Failed to search contact. Please check WhatsApp manually."
        
        # 4. TYPE MESSAGE - Use Tab key to navigate to message box (more reliable than coordinates)
        logger.info(f"✍️ Typing message via clipboard...")
        
        # Press Tab to move focus to message input (works in both Desktop and Web)
        pyautogui.press('tab')
        await asyncio.sleep(0.5)
        pyautogui.press('tab')
        await asyncio.sleep(0.5)
        
        # Click message box area as fallback — use relative position
        # WhatsApp message box is typically at bottom center
        screen_width, screen_height = pyautogui.size()
        message_x = int(screen_width * 0.5)
        message_y = int(screen_height * 0.90)
        pyautogui.click(message_x, message_y)
        await asyncio.sleep(1.0)
        
        # Paste message
        pyperclip.copy(message)
        await asyncio.sleep(0.3)
        pyautogui.hotkey('ctrl', 'v')
        await asyncio.sleep(1.5)
        
        # 5. SEND
        logger.info("📤 Sending...")
        pyautogui.press('enter')
        await asyncio.sleep(0.8)
        logger.info(f"🚀 Message sent!")

        # Update tracking stats
        import time as _time
        global _messages_sent_count, _last_recipient, _last_send_time, _last_send_mode
        _messages_sent_count += 1
        _last_recipient = recipient
        _last_send_time = _time.time()
        _last_send_mode = mode

        return (
            f"✅ Message sent to {recipient}\n"
            f"📡 Delivery Mode: ===[ {mode.upper()} ]===\n"
            f"💬 Message: '{message}'\n"
            f"📊 Session total: {_messages_sent_count} messages sent\n"
            f"Ab tak {_messages_sent_count} message bheje ja chuke hain!"
        )
        
    except Exception as e:
        logger.error(f"WhatsApp error: {e}")
        return f"❌ WhatsApp error: {str(e)}"


@function_tool
async def get_whatsapp_send_stats_tool() -> str:
    """
    📊 WhatsApp Messaging Stats for this session.
    Shows total messages sent, last recipient, last send time, and WhatsApp mode.
    Is session mein kitne message bheje — sab stats yahan milenge!
    """
    import datetime

    if _messages_sent_count == 0:
        return (
            "📊 WhatsApp Send Stats:\n"
            "📭 No messages sent this session.\n"
            "Abhi tak koi message nahi bheja gaya — pehle kuch bhejo!"
        )

    last_time_str = "N/A"
    if _last_send_time:
        dt = datetime.datetime.fromtimestamp(_last_send_time)
        last_time_str = dt.strftime("%Y-%m-%d %H:%M:%S")

    mode_display = (_last_send_mode or "unknown").upper()

    return (
        f"📊 WhatsApp Send Stats / भेजने के आँकड़े:\n"
        f"{'='*45}\n"
        f"📨 Total Messages Sent: {_messages_sent_count}\n"
        f"👤 Last Recipient: {_last_recipient or 'N/A'}\n"
        f"🕐 Last Send Time: {last_time_str}\n"
        f"📡 WhatsApp Mode: ===[ {mode_display} ]===\n"
        f"{'='*45}\n"
        f"Is session mein {_messages_sent_count} messages bheje gaye hain!"
    )
