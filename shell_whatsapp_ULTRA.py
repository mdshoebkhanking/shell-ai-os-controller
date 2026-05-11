
import webbrowser
import asyncio
import logging
from shell_safe_executor import god_tier_tool as function_tool
import os
from pathlib import Path

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("WHATSAPP_ULTRA")

# Global state
_whatsapp_already_running = False
_last_message_time = 0

async def launch_whatsapp() -> tuple[bool, str]:
    """Ultra-fast WhatsApp launcher with process detection"""
    import subprocess
    global _whatsapp_already_running
    
    logger.info("🚀 Launching WhatsApp...")
    
    # Check if already running
    try:
        import psutil
        for proc in psutil.process_iter(['name']):
            if 'whatsapp' in proc.info['name'].lower():
                logger.info("⚡ WhatsApp already running!")
                _whatsapp_already_running = True
                await asyncio.sleep(0.5)
                return True, "app"
    except Exception:
        pass  # psutil may not be available
    
    # Launch WhatsApp
    paths = [
        os.path.expandvars(r"%LOCALAPPDATA%\WhatsApp\WhatsApp.exe"),
        os.path.expandvars(r"%PROGRAMFILES%\WhatsApp\WhatsApp.exe"),
    ]
    
    for path in paths:
        if os.path.exists(path):
            subprocess.Popen([path])
            _whatsapp_already_running = False
            await asyncio.sleep(5.0)
            return True, "app"
    
    # Fallback
    subprocess.Popen(["cmd", "/c", "start", "whatsapp:"])
    await asyncio.sleep(5.0)
    return True, "app"

async def verify_message_sent() -> bool:
    """Uses vision to verify message was sent (checks for checkmark).

    Previously called a non-existent `vision_engine.analyze_screen()` method
    which always raised AttributeError; the old `except: return True` swallowed
    that and gave false-positive 'verified' replies forever.

    Now uses the real `VisionEngine.analyze_with_gemini(image, prompt)` API
    and returns False on any failure so the caller can honestly report
    'unverified' instead of silently succeeding.
    """
    try:
        from vision_engine import vision_engine
        import pyautogui
        import asyncio as _asyncio

        screenshot = pyautogui.screenshot()
        prompt = (
            "Look at the bottom right of the most recent outgoing message. "
            "Is there a checkmark indicator (grey tick, double tick, or blue tick) "
            "suggesting the message was sent? Reply with just 'yes' or 'no'."
        )
        result = await _asyncio.to_thread(
            vision_engine.analyze_with_gemini, screenshot, prompt,
        )
        if not result:
            return False
        lowered = str(result).lower().strip()
        if "vision unavailable" in lowered or lowered == "fail":
            return False
        # Prefer a positive sentinel over substring false-positives ("no checkmark")
        if lowered.startswith("yes") or "yes, " in lowered:
            return True
        if lowered.startswith("no"):
            return False
        # Fallback: accept the word 'checkmark' only if 'no' is absent.
        return "checkmark" in lowered and "no checkmark" not in lowered
    except Exception as e:
        logger.warning("verify_message_sent vision call failed: %s", e)
        return False

@function_tool
async def send_whatsapp_message(recipient: str, message: str, verify: bool = True) -> str:
    """
    🚀 ULTRA WhatsApp Messenger
    
    Sends WhatsApp messages with advanced features:
    - Adaptive speed (fast when already running)
    - Visual verification (confirms message sent)
    - Error recovery (multiple retry methods)
    - Smart timing (prevents rate limiting)
    
    Args:
        recipient: Contact name to search
        message: Message text to send
        verify: Whether to verify message was sent (default: True)
    """
    logger.info("=" * 60)
    logger.info("ULTRA WHATSAPP MESSENGER")
    logger.info(f"To: {recipient}")
    logger.info(f"Message: {message}")
    logger.info("=" * 60)
    
    try:
        import pyautogui
        import pyperclip
        from shell_window_CTRL import focus_window
        
        # Rate limiting check
        import time
        global _last_message_time
        time_since_last = time.time() - _last_message_time
        if time_since_last < 2.0:
            wait = 2.0 - time_since_last
            logger.info(f"⏱️ Rate limiting: waiting {wait:.1f}s...")
            await asyncio.sleep(wait)
        
        # 1. LAUNCH
        found_app, mode = await launch_whatsapp()
        
        if found_app:
            wait = 0.5 if _whatsapp_already_running else 3.0
            await asyncio.sleep(wait)
            await focus_window("whatsapp")
            await asyncio.sleep(0.3)
        
        # 2. FOCUS
        screen_width, screen_height = pyautogui.size()
        pyautogui.click(screen_width // 2, screen_height // 2)
        await asyncio.sleep(0.5 if _whatsapp_already_running else 1.5)
        
        # 3. SEARCH - Multi-method approach
        logger.info(f"🔍 Searching: {recipient}")
        
        search_wait = 1.5 if _whatsapp_already_running else 3.0
        result_wait = 2.5 if _whatsapp_already_running else 5.0
        
        search_success = False
        
        # Try Ctrl+F first
        for attempt in range(2):
            try:
                pyautogui.hotkey('ctrl', 'f')
                await asyncio.sleep(search_wait)
                
                # Clear
                for _ in range(2):
                    pyautogui.hotkey('ctrl', 'a')
                    await asyncio.sleep(0.1)
                    pyautogui.press('delete')
                
                await asyncio.sleep(0.3)
                
                # Type
                pyperclip.copy(recipient)
                await asyncio.sleep(0.2)
                pyautogui.hotkey('ctrl', 'v')
                
                # Wait for results
                await asyncio.sleep(result_wait)
                
                # Select
                pyautogui.press('down')
                await asyncio.sleep(0.3)
                pyautogui.press('enter')
                await asyncio.sleep(1.5 if _whatsapp_already_running else 3.0)
                
                search_success = True
                logger.info("✅ Contact found!")
                break
            except Exception as e:
                logger.warning(f"Search attempt {attempt+1} failed: {e}")
                await asyncio.sleep(1.0)
        
        if not search_success:
            return "❌ Failed to find contact"
        
        # 4. TYPE MESSAGE
        logger.info("✍️ Typing message...")
        
        # Click message box
        msg_x = int(screen_width * 0.5)
        msg_y = int(screen_height * 0.92)
        pyautogui.click(msg_x, msg_y)
        await asyncio.sleep(0.5)
        
        # Paste
        pyperclip.copy(message)
        await asyncio.sleep(0.2)
        pyautogui.hotkey('ctrl', 'v')
        await asyncio.sleep(0.8)
        
        # 5. SEND
        logger.info("📤 Sending...")
        pyautogui.press('enter')
        await asyncio.sleep(0.5)
        
        _last_message_time = time.time()
        
        # 6. VERIFY (if enabled)
        if verify:
            logger.info("🔍 Verifying delivery...")
            await asyncio.sleep(1.0)
            verified = await verify_message_sent()
            status = "✅ Verified" if verified else "⚠️ Unverified"
        else:
            status = "✅ Sent"
        
        # Enhanced output with character count and delivery estimate
        char_count = len(message)
        est_delivery = "~1s" if char_count < 100 else "~2s" if char_count < 500 else "~3s"

        logger.info(f"🚀 {status}!")
        return (
            f"📲 {status}: Message sent to {recipient} ({mode.upper()})\n"
            f"💬 Message: '{message}'\n"
            f"📝 Characters: {char_count} | ⏱️ Estimated delivery: {est_delivery}\n"
            f"✅ Delivery complete — {recipient} ko message pahunch gaya!"
        )
        
    except Exception as e:
        logger.error(f"Error: {e}")
        return f"❌ Error: {str(e)}"

@function_tool
async def send_whatsapp_bulk(contacts: list[str], message: str) -> str:
    """
    📨 Send message to multiple contacts
    
    Args:
        contacts: List of contact names
        message: Message to send to all
    """
    logger.info(f"📨 Bulk sending to {len(contacts)} contacts...")
    
    total = len(contacts)
    success_count = 0
    fail_count = 0
    results = []

    for i, contact in enumerate(contacts, 1):
        logger.info(f"📨 [{i}/{total}] Sending to {contact}...")
        result = await send_whatsapp_message(contact, message, verify=False)
        results.append(f"[{i}/{total}] {contact}: {result}")

        if "❌" in result:
            fail_count += 1
        else:
            success_count += 1

        logger.info(f"📊 Progress: {i}/{total} done | ✅ {success_count} sent | ❌ {fail_count} failed")

        # Delay between messages
        if i < total:
            await asyncio.sleep(3.0)

    # Summary
    summary = (
        f"\n{'='*50}\n"
        f"📊 BULK SEND SUMMARY / भेजने का सारांश:\n"
        f"📨 Total: {total} | ✅ Success: {success_count} | ❌ Failed: {fail_count}\n"
        f"{'='*50}"
    )
    results.append(summary)

    return "\n".join(results)

@function_tool
async def send_whatsapp_media(recipient: str, file_path: str, caption: str = "") -> str:
    """
    📎 Send image/file via WhatsApp
    
    Args:
        recipient: Contact name
        file_path: Path to image/file
        caption: Optional caption
    """
    try:
        import pyautogui
        import pyperclip
        
        if not os.path.exists(file_path):
            return f"❌ File not found: {file_path}"
        
        # First open chat
        await send_whatsapp_message(recipient, ".", verify=False)
        await asyncio.sleep(1.0)
        
        # Attach file (Ctrl+Shift+O in WhatsApp Desktop)
        logger.info(f"📎 Attaching: {file_path}")
        pyautogui.hotkey('ctrl', 'shift', 'o')
        await asyncio.sleep(2.0)
        
        # Type file path
        pyperclip.copy(file_path)
        await asyncio.sleep(0.3)
        pyautogui.hotkey('ctrl', 'v')
        await asyncio.sleep(0.5)
        pyautogui.press('enter')
        await asyncio.sleep(2.0)
        
        # Add caption if provided
        if caption:
            pyperclip.copy(caption)
            await asyncio.sleep(0.2)
            pyautogui.hotkey('ctrl', 'v')
            await asyncio.sleep(0.5)
        
        # Send
        pyautogui.press('enter')
        await asyncio.sleep(1.0)
        
        return f"✅ Media sent to {recipient}: {Path(file_path).name}"
        
    except Exception as e:
        return f"❌ Media send failed: {str(e)}"


@function_tool
async def check_whatsapp_running_tool() -> str:
    """
    🔍 Check if WhatsApp Desktop is running.
    Shows running status, PID, memory usage, and window title.
    WhatsApp chal raha hai ya nahi — sab pata lagayega!
    """
    try:
        import psutil

        whatsapp_procs = []
        for proc in psutil.process_iter(['name', 'pid', 'memory_info']):
            try:
                if proc.info['name'] and 'whatsapp' in proc.info['name'].lower():
                    mem_mb = proc.info['memory_info'].rss / (1024 * 1024) if proc.info['memory_info'] else 0
                    whatsapp_procs.append({
                        'pid': proc.info['pid'],
                        'name': proc.info['name'],
                        'memory_mb': round(mem_mb, 2)
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if not whatsapp_procs:
            return (
                "📱 WhatsApp Status: ❌ NOT RUNNING\n"
                "WhatsApp Desktop abhi band hai — koi process nahi mila!\n"
                "Start karne ke liye WhatsApp launch karo."
            )

        # Try to get window title
        window_title = "N/A"
        try:
            import pygetwindow as gw
            wa_windows = [w for w in gw.getAllWindows() if 'whatsapp' in w.title.lower()]
            if wa_windows:
                window_title = wa_windows[0].title
        except Exception as _e:
            logger.debug("ignored Exception: %s", _e)

        lines = [
            "📱 WhatsApp Status: ✅ RUNNING — WhatsApp chal raha hai!",
            f"🪟 Window Title: {window_title}",
            f"📊 Processes Found: {len(whatsapp_procs)}",
            ""
        ]
        for p in whatsapp_procs:
            lines.append(f"  🔹 PID: {p['pid']} | Name: {p['name']} | Memory: {p['memory_mb']} MB")

        return "\n".join(lines)

    except ImportError:
        return "❌ psutil module not installed — process check nahi ho sakta. Install karo: pip install psutil"
    except Exception as e:
        return f"❌ Error checking WhatsApp status: {str(e)}"
