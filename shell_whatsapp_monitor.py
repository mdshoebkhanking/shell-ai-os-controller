"""
🤖 Shell WhatsApp Monitor - Auto-Reply System

This module monitors WhatsApp for incoming messages and auto-responds
when you message yourself from your phone. Shell becomes your AI assistant
accessible via WhatsApp!

Features:
- Continuous message monitoring
- Auto-reply to your own messages
- OCR-based message reading
- AI-powered responses
"""

import asyncio
import logging
import time
import os
import json
from datetime import datetime
import pyautogui
import pyperclip
from shell_safe_executor import god_tier_tool as function_tool

logger = logging.getLogger("WHATSAPP_MONITOR")

# Global state
_monitoring_active = False
_last_checked_time = 0
_your_contact_name = "Me"  # WhatsApp shows your own messages as "Me" or your name
_monitor_start_time = 0.0
_messages_processed = 0
_last_error_msg = ""
_last_error_time = ""

async def read_latest_message() -> tuple[str, str]:
    """
    Reads the latest WhatsApp message using OCR
    Returns: (sender_name, message_text)
    """
    try:
        from vision_engine import vision_engine
        
        # Take screenshot of chat area
        screen_width, screen_height = pyautogui.size()
        
        # Focus on chat area (right side of WhatsApp)
        chat_x = int(screen_width * 0.7)
        chat_y = int(screen_height * 0.5)
        
        # Use vision to read latest message
        result = await vision_engine.analyze_screen(
            task="Read the most recent WhatsApp message. Return format: 'SENDER: message text'"
        )
        
        # Parse result
        if ":" in result:
            parts = result.split(":", 1)
            sender = parts[0].strip()
            message = parts[1].strip()
            return sender, message
        
        return "", ""
        
    except Exception as e:
        logger.error(f"Error reading message: {e}")
        return "", ""

async def send_reply(message: str):
    """Sends a reply in the current WhatsApp chat"""
    try:
        screen_width, screen_height = pyautogui.size()
        
        # Click message box
        msg_x = int(screen_width * 0.7)
        msg_y = int(screen_height * 0.92)
        pyautogui.click(msg_x, msg_y)
        await asyncio.sleep(0.3)
        
        # Type and send
        pyperclip.copy(message)
        await asyncio.sleep(0.2)
        pyautogui.hotkey('ctrl', 'v')
        await asyncio.sleep(0.5)
        pyautogui.press('enter')
        
        logger.info(f"✅ Replied: {message}")
        
    except Exception as e:
        logger.error(f"Error sending reply: {e}")

async def process_message_with_ai(message: str) -> str:
    """
    Processes user message with Shell's AI brain
    Returns: AI-generated response
    """
    try:
        # Import Shell's brain
        from shell_brain import ShellBrain
        
        # Get AI response
        brain = ShellBrain()
        response = await brain.process_query(message)
        
        return response
        
    except Exception as e:
        logger.error(f"AI processing error: {e}")
        # Fallback responses
        responses = {
            "hello": "Hi! Shell here. How can I help?",
            "status": "I'm running on your PC, all systems operational! 🚀",
            "help": "I can help with tasks, answer questions, and control your PC remotely!",
        }
        
        msg_lower = message.lower()
        for key, response in responses.items():
            if key in msg_lower:
                return response
        
        return "I received your message! Shell AI is processing... 🤖"

async def monitor_whatsapp_loop():
    """Main monitoring loop - runs continuously"""
    global _last_checked_time, _messages_processed, _last_error_msg, _last_error_time

    logger.info("🔍 WhatsApp Monitor started!")

    while _monitoring_active:
        try:
            # Check for new messages every 5 seconds
            await asyncio.sleep(5.0)

            # Read latest message
            sender, message = await read_latest_message()

            # Check if it's from you (your own number)
            if sender and (sender.lower() in ["me", "you", _your_contact_name.lower()]):

                # Check if this is a new message (not already processed)
                current_time = time.time()
                if current_time - _last_checked_time < 3:
                    continue  # Skip if we just processed a message

                logger.info(f"📱 New message from YOU: {message}")

                # Process with AI
                response = await process_message_with_ai(message)

                # Send reply
                await send_reply(response)

                _last_checked_time = current_time
                _messages_processed += 1

        except Exception as e:
            _last_error_msg = str(e)
            _last_error_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.error(f"Monitor loop error: {e}")
            await asyncio.sleep(5.0)

    logger.info("🛑 WhatsApp Monitor stopped")

@function_tool
async def start_whatsapp_monitor(your_name: str = "Me") -> str:
    """
    🤖 Start WhatsApp Auto-Reply Monitor
    
    Shell will monitor WhatsApp and auto-reply when you message yourself.
    Perfect for remote control when you're away from PC!
    
    Args:
        your_name: Your contact name in WhatsApp (default: "Me")
    """
    global _monitoring_active, _your_contact_name, _monitor_start_time, _messages_processed, _last_error_msg, _last_error_time

    if _monitoring_active:
        return "⚠️ Monitor pehle se chal raha hai!"

    _your_contact_name = your_name
    _monitoring_active = True
    _monitor_start_time = time.time()
    _messages_processed = 0
    _last_error_msg = ""
    _last_error_time = ""

    # Start monitoring in background
    asyncio.create_task(monitor_whatsapp_loop())
    
    logger.info(f"✅ WhatsApp Monitor started! Watching for messages from: {your_name}")
    return f"✅ WhatsApp Auto-Reply activated! Shell will respond to messages from '{your_name}' 🤖"

@function_tool
async def stop_whatsapp_monitor() -> str:
    """Stop WhatsApp monitoring"""
    global _monitoring_active
    
    if not _monitoring_active:
        return "⚠️ Monitor not running"
    
    _monitoring_active = False
    logger.info("🛑 WhatsApp Monitor stopped")
    return "🛑 WhatsApp Auto-Reply deactivated"

@function_tool
async def whatsapp_monitor_status() -> str:
    """Check WhatsApp monitor status — uptime, message count, aur last error bhi dikhata hai."""
    if _monitoring_active:
        # Calculate uptime
        uptime_seconds = int(time.time() - _monitor_start_time)
        hours, remainder = divmod(uptime_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours > 0:
            uptime_str = f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            uptime_str = f"{minutes}m {seconds}s"
        else:
            uptime_str = f"{seconds}s"

        status = (
            f"✅ **WhatsApp Monitor: ACTIVE**\n"
            f"👤 Watching messages from: {_your_contact_name}\n"
            f"⏱️ Uptime: {uptime_str}\n"
            f"📨 Messages processed: {_messages_processed}"
        )

        if _last_error_msg:
            status += f"\n🔴 Last error: {_last_error_msg} ({_last_error_time})"
        else:
            status += "\n🟢 No errors — sab smooth chal raha hai"

        return status
    else:
        return "❌ Monitor inactive hai. 'Start whatsapp monitor' bolo activate karne ke liye."

@function_tool
async def set_whatsapp_contact_name(name: str) -> str:
    """
    Set your WhatsApp contact name for monitoring

    Args:
        name: Your contact name as shown in WhatsApp
    """
    global _your_contact_name
    _your_contact_name = name
    return f"✅ Contact name set to: {name}"


@function_tool
async def get_whatsapp_monitor_stats_tool() -> str:
    """📊 Comprehensive WhatsApp monitoring stats dikhata hai — total messages, unique contacts,
    average response time, AI provider usage breakdown, error count. Reply log se data padh ke report banata hai."""
    try:
        PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
        reply_log_file = os.path.join(PROJECT_ROOT, ".whatsapp_reply_log.json")

        log = []
        if os.path.isfile(reply_log_file):
            with open(reply_log_file, "r", encoding="utf-8") as f:
                log = json.load(f)

        total_messages = len(log)
        unique_contacts = set()
        provider_counts = {}
        error_count = 0

        for entry in log:
            sender = entry.get("sender", "Unknown")
            unique_contacts.add(sender)

            provider = entry.get("provider", "unknown")
            provider_counts[provider] = provider_counts.get(provider, 0) + 1

            if provider == "fallback":
                error_count += 1  # fallback matlab AI providers fail hue

        # Uptime info
        if _monitoring_active and _monitor_start_time > 0:
            uptime_seconds = int(time.time() - _monitor_start_time)
            hours, remainder = divmod(uptime_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            if hours > 0:
                uptime_str = f"{hours}h {minutes}m {seconds}s"
            elif minutes > 0:
                uptime_str = f"{minutes}m {seconds}s"
            else:
                uptime_str = f"{seconds}s"
            monitor_status = f"✅ Active (uptime: {uptime_str})"
        else:
            monitor_status = "❌ Inactive"

        # Average response time estimate (based on session)
        if _monitoring_active and _messages_processed > 0 and _monitor_start_time > 0:
            elapsed = time.time() - _monitor_start_time
            avg_interval = elapsed / _messages_processed
            avg_str = f"{avg_interval:.1f}s (average interval between replies)"
        else:
            avg_str = "N/A — monitor active nahi ya koi message process nahi hua"

        # Provider breakdown
        provider_lines = []
        for prov, count in sorted(provider_counts.items(), key=lambda x: -x[1]):
            pct = (count / total_messages * 100) if total_messages > 0 else 0
            provider_lines.append(f"  • {prov}: {count} ({pct:.1f}%)")
        provider_str = "\n".join(provider_lines) if provider_lines else "  Koi data nahi hai abhi"

        # Error info
        error_line = ""
        if _last_error_msg:
            error_line = f"\n🔴 Last runtime error: {_last_error_msg} ({_last_error_time})"

        report = (
            f"📊 **WhatsApp Monitor — Full Stats**\n\n"
            f"🖥️ Monitor: {monitor_status}\n"
            f"📨 Total messages (log): {total_messages}\n"
            f"📨 Session messages: {_messages_processed}\n"
            f"👤 Unique contacts: {len(unique_contacts)}\n"
            f"⏱️ Avg response interval: {avg_str}\n\n"
            f"🤖 **AI Provider Breakdown:**\n{provider_str}\n\n"
            f"⚠️ Fallback replies (AI fail): {error_count}"
            f"{error_line}\n\n"
            f"Sab kuch smooth chal raha hai, boss! 💪"
        )

        return report
    except Exception as e:
        return f"❌ Stats generate karte waqt error: {e}"
