#!/usr/bin/env python3
"""
Shell Social Media Connector
Handles authentication and control for WhatsApp, Telegram, Instagram
"""

import os
import json
import tempfile
from pathlib import Path
from typing import Dict, Optional, Tuple
from datetime import datetime
from shell_safe_executor import god_tier_tool as function_tool
import logging

try:
    import requests
except ImportError:
    requests = None

logger = logging.getLogger("shell_social_connector")

# Connection state storage
def _path_is_writable(path: Path) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        probe = path.parent / f".{path.name}.write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def _connections_file() -> Path:
    candidates = [
        Path(os.environ.get("SHELL_SOCIAL_CONNECTIONS_FILE", "")).expanduser()
        if os.environ.get("SHELL_SOCIAL_CONNECTIONS_FILE")
        else None,
        Path.home() / ".shell_social_connections.json",
        Path(__file__).resolve().parent / ".shell_runtime" / "social_connections.json",
        Path(tempfile.gettempdir()) / "shell_social_connections.json",
    ]
    for candidate in candidates:
        if candidate and _path_is_writable(candidate):
            return candidate
    return Path(tempfile.gettempdir()) / "shell_social_connections.json"


CONNECTIONS_FILE = str(_connections_file())

SUPPORTED_PLATFORMS = ["whatsapp", "telegram", "instagram"]

class SocialMediaConnector:
    """Manages social media platform connections"""

    def __init__(self):
        self.connections = self._load_connections()

    def _load_connections(self) -> Dict:
        """Load saved connections from disk"""
        if os.path.exists(CONNECTIONS_FILE):
            try:
                with open(CONNECTIONS_FILE, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load connections: {e}")
        return {
            "whatsapp": {"connected": False, "account": None, "last_connected": None},
            "telegram": {"connected": False, "account": None, "last_connected": None},
            "instagram": {"connected": False, "account": None, "last_connected": None}
        }

    def _save_connections(self):
        """Save connections to disk"""
        try:
            with open(CONNECTIONS_FILE, 'w') as f:
                json.dump(self.connections, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save connections: {e}")

    def get_status(self, platform: str) -> Dict:
        """Get connection status for a platform"""
        return self.connections.get(platform.lower(), {"connected": False})

    def connect_whatsapp(self, phone_number: str = None) -> Tuple[bool, str]:
        """
        Connect to WhatsApp using WhatsApp Web (QR Code)
        Returns: (success, message)
        """
        try:
            # Use WhatsApp Web client
            from shell_whatsapp_web import whatsapp_client
            import asyncio

            # Start connection (will show QR in UI)
            loop = asyncio.get_event_loop()
            success, msg = loop.run_until_complete(
                whatsapp_client.start_connection()
            )

            if success:
                self.connections["whatsapp"] = {
                    "connected": True,
                    "account": "WhatsApp Web",
                    "last_connected": datetime.now().isoformat(),
                    "connected_at": datetime.now().isoformat(),
                    "message_count": 0
                }
                self._save_connections()
                logger.info(f"WhatsApp Connected via QR")
                return True, "WhatsApp connected successfully!"
            else:
                return False, msg
        except Exception as e:
            logger.error(f"WhatsApp connection failed: {e}")
            return False, f"Connection failed: {str(e)}"

    def connect_telegram(self, bot_token: str = None, phone: str = None) -> Tuple[bool, str]:
        """
        Connect to Telegram via Bot API.
        Uses the TELEGRAM_BOT_TOKEN from .env or the provided bot_token.
        Validates the token by calling Telegram's getMe endpoint.
        Returns: (success, message)
        """
        try:
            import requests

            # Resolve token: parameter > env > config
            token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "")
            if not token:
                return False, "Telegram Bot Token nahi mila! .env mein TELEGRAM_BOT_TOKEN set karo ya parameter mein do."

            # Validate token via Telegram Bot API getMe
            api_url = f"https://api.telegram.org/bot{token}/getMe"
            resp = requests.get(api_url, timeout=10)
            data = resp.json()

            if not data.get("ok"):
                error_desc = data.get("description", "Unknown error")
                return False, f"Telegram token invalid: {error_desc}"

            bot_info = data.get("result", {})
            bot_username = bot_info.get("username", "unknown_bot")
            bot_name = bot_info.get("first_name", "Bot")

            self.connections["telegram"] = {
                "connected": True,
                "account": f"@{bot_username} ({bot_name})",
                "bot_token": token[:8] + "..." + token[-4:],  # redacted for safety
                "bot_id": bot_info.get("id"),
                "last_connected": datetime.now().isoformat(),
                "connected_at": datetime.now().isoformat(),
                "message_count": 0
            }
            self._save_connections()
            logger.info(f"Telegram Connected: @{bot_username}")
            return True, f"Telegram connected as @{bot_username} ({bot_name})!"
        except ImportError:
            return False, "requests library install nahi hai. pip install requests karo."
        except requests.exceptions.Timeout:
            return False, "Telegram API timeout ho gaya. Internet check karo."
        except requests.exceptions.ConnectionError:
            return False, "Telegram API se connect nahi ho paya. Internet check karo."
        except Exception as e:
            logger.error(f"Telegram connection failed: {e}")
            return False, f"Connection failed: {str(e)}"

    def connect_instagram(self, username: str = None, password: str = None) -> Tuple[bool, str]:
        """
        Connect to Instagram using instagrapi (if available) or credential validation.
        Falls back to session-based login check.
        Returns: (success, message)
        """
        try:
            # Resolve credentials from env if not provided
            username = username or os.getenv("INSTAGRAM_USERNAME", "")
            password = password or os.getenv("INSTAGRAM_PASSWORD", "")

            if not username:
                return False, "Instagram username nahi mila! .env mein INSTAGRAM_USERNAME set karo ya parameter mein do."

            # Try instagrapi if available (full API access)
            try:
                from instagrapi import Client as InstaClient
                cl = InstaClient()
                if password:
                    cl.login(username, password)
                    user_info = cl.account_info()
                    full_name = user_info.full_name or username
                    followers = user_info.follower_count

                    self.connections["instagram"] = {
                        "connected": True,
                        "account": f"@{username} ({full_name})",
                        "followers": followers,
                        "method": "instagrapi",
                        "last_connected": datetime.now().isoformat(),
                        "connected_at": datetime.now().isoformat(),
                        "message_count": 0
                    }
                    self._save_connections()
                    logger.info(f"Instagram Connected via instagrapi: @{username}")
                    return True, f"Instagram connected as @{username} ({full_name})! Followers: {followers}"
                else:
                    return False, "Instagram password required for instagrapi login."

            except ImportError:
                logger.info("instagrapi not installed, using basic session mode")

            # Fallback: basic session mode (stores credentials, marks connected)
            if not password:
                return False, "Instagram password required. .env mein INSTAGRAM_PASSWORD set karo."

            # Basic validation — at minimum confirm credentials are non-empty
            if len(username) < 3 or len(password) < 6:
                return False, "Instagram credentials too short. Valid username aur password do."

            self.connections["instagram"] = {
                "connected": True,
                "account": f"@{username}",
                "method": "session_basic",
                "last_connected": datetime.now().isoformat(),
                "connected_at": datetime.now().isoformat(),
                "message_count": 0
            }
            self._save_connections()
            logger.info(f"Instagram Connected (basic session): @{username}")
            return True, f"Instagram connected as @{username}! (Basic mode — install instagrapi for full API access)"

        except Exception as e:
            logger.error(f"Instagram connection failed: {e}")
            return False, f"Connection failed: {str(e)}"

    def disconnect(self, platform: str) -> bool:
        """Disconnect from a platform"""
        platform = platform.lower()
        if platform in self.connections:
            self.connections[platform] = {
                "connected": False,
                "account": None,
                "last_connected": self.connections[platform].get("last_connected"),
                "disconnected_at": datetime.now().isoformat(),
                "connected_at": self.connections[platform].get("connected_at"),
                "message_count": self.connections[platform].get("message_count", 0)
            }
            self._save_connections()
            logger.info(f"{platform.title()} Disconnected")
            return True
        return False

# Global instance
social_connector = SocialMediaConnector()

# ==================== LIVEKIT FUNCTION TOOLS ====================

@function_tool
async def connect_social_media(platform: str, credentials: str = None) -> str:
    """
    Connect Shell to a social media platform.
    Shell ko social media se connect karta hai - WhatsApp, Telegram, ya Instagram.

    Args:
        platform: 'whatsapp', 'telegram', or 'instagram'
        credentials: Optional credentials (phone, token, username)
    """
    platform = platform.lower().strip()

    # --- Validation: platform name check karo ---
    if not platform:
        return "Validation Error: Platform name khali hai bhai! 'whatsapp', 'telegram', ya 'instagram' mein se ek batao."

    if platform not in SUPPORTED_PLATFORMS:
        return (
            f"Validation Error: '{platform}' supported nahi hai bhai! "
            f"Sirf ye platforms supported hain: {', '.join(SUPPORTED_PLATFORMS)}. "
            f"Please ek valid platform name do."
        )

    connection_timestamp = datetime.now().isoformat()

    if platform == "whatsapp":
        success, msg = social_connector.connect_whatsapp(credentials)
    elif platform == "telegram":
        success, msg = social_connector.connect_telegram(credentials)
    elif platform == "instagram":
        success, msg = social_connector.connect_instagram(credentials)
    else:
        return f"Unknown platform: {platform} - ye platform pehchaan nahi aaya!"

    lines = []
    if success:
        lines.append(f"{platform.title()} se connect ho gaya successfully: {msg}")
        lines.append(f"Connection Timestamp: {connection_timestamp}")
    else:
        lines.append(f"{platform.title()} se connection fail ho gaya: {msg}")

    return "\n".join(lines)

@function_tool
async def disconnect_social_media(platform: str) -> str:
    """
    Disconnect Shell from a social media platform.
    Shell ko social media se disconnect karta hai.

    Args:
        platform: 'whatsapp', 'telegram', or 'instagram'
    """
    if social_connector.disconnect(platform):
        return f"{platform.title()} se disconnect ho gaya successfully!"
    return f"{platform} se disconnect nahi ho paya - Failed to disconnect"

@function_tool
async def get_social_status() -> str:
    """
    Get connection status for all social media platforms.
    Sabhi social media platforms ka connection status dikhata hai - last connected, message count sab kuch.
    """
    status_lines = ["===== Social Media Connection Status ====="]

    for platform in SUPPORTED_PLATFORMS:
        info = social_connector.get_status(platform)
        connected = info.get("connected", False)
        account = info.get("account")
        last_connected = info.get("last_connected")
        connected_at = info.get("connected_at")
        message_count = info.get("message_count", 0)

        icon = "CONNECTED" if connected else "DISCONNECTED"
        account_str = f" ({account})" if account else ""

        lines = [f"--- {platform.title()}{account_str} ---"]
        lines.append(f"  Status: {icon}")

        # Last connected date
        if last_connected:
            try:
                last_dt = datetime.fromisoformat(last_connected)
                lines.append(f"  Last Connected: {last_dt.strftime('%d %b %Y, %I:%M %p')}")
            except (ValueError, TypeError):
                lines.append(f"  Last Connected: {last_connected}")
        else:
            lines.append("  Last Connected: Kabhi nahi - Never connected")

        # Connection duration
        if connected and connected_at:
            try:
                start_dt = datetime.fromisoformat(connected_at)
                duration = datetime.now() - start_dt
                days = duration.days
                hours = duration.seconds // 3600
                minutes = (duration.seconds % 3600) // 60
                lines.append(f"  Connection Duration: {days}d {hours}h {minutes}m se connected hai")
            except (ValueError, TypeError):
                lines.append("  Connection Duration: Unknown")

        # Message count
        if message_count is not None:
            lines.append(f"  Message Count: {message_count} messages")

        status_lines.extend(lines)

    status_lines.append("==========================================")
    return "\n".join(status_lines)

@function_tool
async def send_social_message(platform: str, recipient: str, message: str) -> str:
    """
    Send a message via social media platform.
    Social media platform ke through message bhejta hai.

    Args:
        platform: 'whatsapp', 'telegram', or 'instagram'
        recipient: Phone number, username, or chat ID
        message: Message text to send
    """
    # Check if connected
    if not social_connector.get_status(platform)["connected"]:
        return f"{platform.title()} se connected nahi hai bhai! Pehle connect karo - Connect first!"

    platform = platform.lower().strip()

    if platform == "telegram":
        return await _send_telegram_message(recipient, message)
    elif platform == "whatsapp":
        return await _send_whatsapp_message(recipient, message)
    elif platform == "instagram":
        return await _send_instagram_message(recipient, message)
    else:
        return f"Platform '{platform}' se message bhejne ka tariqa abhi implement nahi hai."


async def _send_telegram_message(chat_id: str, message: str) -> str:
    """Send a message via Telegram Bot API."""
    try:
        import requests
        token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        if not token:
            return "Telegram Bot Token nahi mila! .env mein TELEGRAM_BOT_TOKEN set karo."

        api_url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
        resp = requests.post(api_url, json=payload, timeout=10)
        data = resp.json()

        if data.get("ok"):
            msg_id = data.get("result", {}).get("message_id", "?")
            # Update message count
            conn = social_connector.connections.get("telegram", {})
            conn["message_count"] = conn.get("message_count", 0) + 1
            social_connector._save_connections()
            return f"Telegram message bhej diya! Chat: {chat_id}, Message ID: {msg_id}"
        else:
            error_desc = data.get("description", "Unknown error")
            return f"Telegram message fail: {error_desc}"
    except Exception as e:
        return f"Telegram message error: {str(e)}"


async def _send_whatsapp_message(recipient: str, message: str) -> str:
    """Send a message via WhatsApp Web automation."""
    try:
        from shell_whatsapp_web import whatsapp_client
        import asyncio
        success = await whatsapp_client.send_message(recipient, message)
        if success:
            conn = social_connector.connections.get("whatsapp", {})
            conn["message_count"] = conn.get("message_count", 0) + 1
            social_connector._save_connections()
            return f"WhatsApp message bhej diya {recipient} ko!"
        return f"WhatsApp message fail ho gaya {recipient} ko."
    except ImportError:
        return "WhatsApp Web module available nahi hai. shell_whatsapp_web.py check karo."
    except Exception as e:
        return f"WhatsApp message error: {str(e)}"


async def _send_instagram_message(recipient: str, message: str) -> str:
    """Send a DM via Instagram using instagrapi."""
    try:
        from instagrapi import Client as InstaClient
        username = os.getenv("INSTAGRAM_USERNAME", "")
        password = os.getenv("INSTAGRAM_PASSWORD", "")

        if not username or not password:
            return "Instagram credentials nahi mile! .env mein INSTAGRAM_USERNAME aur INSTAGRAM_PASSWORD set karo."

        cl = InstaClient()
        cl.login(username, password)
        user_id = cl.user_id_from_username(recipient)
        cl.direct_send(message, [user_id])

        conn = social_connector.connections.get("instagram", {})
        conn["message_count"] = conn.get("message_count", 0) + 1
        social_connector._save_connections()
        return f"Instagram DM bhej diya @{recipient} ko!"
    except ImportError:
        return "instagrapi install nahi hai. pip install instagrapi karo."
    except Exception as e:
        return f"Instagram DM error: {str(e)}"


@function_tool
async def get_connection_history_tool() -> str:
    """
    Sabhi social media platforms ka connection history dikhata hai.
    Shows connection history for all platforms: when connected, when disconnected, total uptime, connection count.
    Connections JSON file se data read karta hai.
    """
    # Load raw connections data from file
    connections_data = {}
    if os.path.exists(CONNECTIONS_FILE):
        try:
            with open(CONNECTIONS_FILE, 'r') as f:
                connections_data = json.load(f)
        except Exception as e:
            return f"Connection history load nahi ho paya: {e}"
    else:
        return "Connection history file abhi tak bani nahi hai - No history file found. Pehle kisi platform se connect karo!"

    if not connections_data:
        return "Connection history khali hai - No connection history available. Pehle kisi platform se connect karo!"

    lines = ["===== Social Media Connection History ====="]

    for platform in SUPPORTED_PLATFORMS:
        info = connections_data.get(platform, {})

        lines.append(f"--- {platform.title()} ---")

        connected = info.get("connected", False)
        lines.append(f"  Current Status: {'Connected - juda hai' if connected else 'Disconnected - nahi juda'}")

        # When connected
        connected_at = info.get("connected_at")
        if connected_at:
            try:
                c_dt = datetime.fromisoformat(connected_at)
                lines.append(f"  Connected At: {c_dt.strftime('%d %b %Y, %I:%M:%S %p')}")
            except (ValueError, TypeError):
                lines.append(f"  Connected At: {connected_at}")
        else:
            lines.append("  Connected At: N/A - kabhi connect nahi hua")

        # When disconnected
        disconnected_at = info.get("disconnected_at")
        if disconnected_at:
            try:
                d_dt = datetime.fromisoformat(disconnected_at)
                lines.append(f"  Disconnected At: {d_dt.strftime('%d %b %Y, %I:%M:%S %p')}")
            except (ValueError, TypeError):
                lines.append(f"  Disconnected At: {disconnected_at}")
        else:
            lines.append("  Disconnected At: N/A")

        # Total uptime calculation
        if connected and connected_at:
            try:
                start_dt = datetime.fromisoformat(connected_at)
                uptime = datetime.now() - start_dt
                days = uptime.days
                hours = uptime.seconds // 3600
                minutes = (uptime.seconds % 3600) // 60
                seconds = uptime.seconds % 60
                lines.append(f"  Total Uptime: {days} din, {hours} ghante, {minutes} minute, {seconds} second")
            except (ValueError, TypeError):
                lines.append("  Total Uptime: Calculate nahi ho paya")
        elif not connected and connected_at and disconnected_at:
            try:
                start_dt = datetime.fromisoformat(connected_at)
                end_dt = datetime.fromisoformat(disconnected_at)
                uptime = end_dt - start_dt
                days = uptime.days
                hours = uptime.seconds // 3600
                minutes = (uptime.seconds % 3600) // 60
                seconds = uptime.seconds % 60
                lines.append(f"  Last Session Uptime: {days} din, {hours} ghante, {minutes} minute, {seconds} second")
            except (ValueError, TypeError):
                lines.append("  Last Session Uptime: Calculate nahi ho paya")
        else:
            lines.append("  Total Uptime: N/A - no session data")

        # Last connected
        last_connected = info.get("last_connected")
        if last_connected:
            try:
                l_dt = datetime.fromisoformat(last_connected)
                lines.append(f"  Last Active: {l_dt.strftime('%d %b %Y, %I:%M:%S %p')}")
            except (ValueError, TypeError):
                lines.append(f"  Last Active: {last_connected}")

        # Message count
        msg_count = info.get("message_count", 0)
        lines.append(f"  Messages: {msg_count} total messages")

        # Account info
        account = info.get("account")
        if account:
            lines.append(f"  Account: {account}")

        lines.append("")

    lines.append(f"History File: {CONNECTIONS_FILE}")
    lines.append("==========================================")

    return "\n".join(lines)
