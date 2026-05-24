#!/usr/bin/env python3
# =============================================================================
# Shell Telegram bot integration
# =============================================================================
# Advanced Telegram Bot with:
# - ✅ Multi-User Support (Admin + Authorized Users)
# - ✅ Group Chat Management
# - ✅ Channel Broadcasting
# - ✅ Inline Keyboard & Buttons
# - ✅ File/Media Handling (Photos, Documents, Voice)
# - Advanced PC control through approved tools
# - Multi-provider AI routing when configured
# - Conversation memory and context
# - Command system, scheduled messages, and auto-reply rules
# - Analytics, rate limiting, and security controls
# - Webhook support as an alternative to polling
# - Custom commands and plugin-ready extension points
# =============================================================================

import os
import sys
import asyncio
import logging
import json
import re
import subprocess
import urllib.request
import urllib.parse
import urllib.error
import time
import hashlib
import base64
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any, Callable
from functools import wraps, lru_cache
from dataclasses import dataclass, field, asdict
from enum import Enum
import threading
from collections import deque, defaultdict
import traceback
import html

# PIL for image handling
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# Function tool
try:
    from shell_safe_executor import god_tier_tool as function_tool
    FUNCTION_TOOL_AVAILABLE = True
except ImportError:
    FUNCTION_TOOL_AVAILABLE = False
    def function_tool(func):
        return func

# Shell AI infrastructure
from shell_config import config
from shell_logger import get_logger

# =============================================================================
# 📊 CONFIGURATION
# =============================================================================

class Config:
    """Telegram bot configuration."""
    
    # API & Tokens
    TELEGRAM_BOT_TOKEN = config.get_str("TELEGRAM_BOT_TOKEN")
    
    # File Paths
    PROJECT_ROOT = Path(__file__).parent
    STATE_FILE = PROJECT_ROOT / ".telegram_state.json"
    LOG_FILE = PROJECT_ROOT / ".telegram_log.json"
    USERS_FILE = PROJECT_ROOT / ".telegram_users.json"
    RULES_FILE = PROJECT_ROOT / ".telegram_rules.json"
    SCHEDULE_FILE = PROJECT_ROOT / ".telegram_schedule.json"
    
    # Limits
    MAX_LOG_ENTRIES = 500
    MAX_HISTORY_PER_USER = 50
    MAX_MESSAGE_LENGTH = 4096  # Telegram limit
    MAX_PHOTO_SIZE_MB = 10
    MAX_FILE_SIZE_MB = 50
    
    # Rate Limiting
    RATE_LIMIT_MESSAGES_PER_MINUTE = 30
    RATE_LIMIT_WINDOW = 60  # seconds
    
    # Security
    ADMIN_CHAT_IDS = []  # Will be populated from env
    ALLOWED_USERS = []  # Whitelist
    BLOCKED_USERS = []  # Blacklist
    REMOTE_CONTROL_ENABLED = False
    ALLOW_TERMINAL = False
    
    # Bot Settings
    BOT_NAME = "Shell AI"
    BOT_USERNAME = "ShellAIBot"
    DEFAULT_LANGUAGE = "en"  # en, hi, hinglish
    
    # AI Settings
    AI_PROVIDERS = ["groq", "perplexity", "claude", "gemini"]
    AI_TEMPERATURE = 0.7
    AI_MAX_TOKENS = 512
    
    # Features
    ENABLE_GROUPS = True
    ENABLE_CHANNELS = True
    ENABLE_INLINE = True
    ENABLE_WEBHOOK = False
    
    # Logging
    LOG_LEVEL = logging.INFO
    LOG_FILE_PATH = "shell_telegram.log"


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "enabled"}


def _parse_chat_ids(value: Any) -> List[int]:
    ids: List[int] = []
    for part in re.split(r"[,;\s]+", str(value or "")):
        part = part.strip()
        if not part:
            continue
        try:
            ids.append(int(part))
        except ValueError:
            continue
    return ids


def _telegram_token_shape_ok(token: str) -> bool:
    """Validate BotFather token shape without making a network call."""
    return bool(re.match(r"^\d{5,20}:[A-Za-z0-9_-]{20,}$", str(token or "").strip()))


def _redact_secret(value: str, visible: int = 4) -> str:
    text = str(value or "").strip()
    if not text:
        return "missing"
    if len(text) <= visible * 2:
        return "configured"
    return f"{text[:visible]}...{text[-visible:]}"


def _platform_label() -> str:
    if sys.platform.startswith("win"):
        return "Windows"
    if sys.platform == "darwin":
        return "macOS"
    if sys.platform.startswith("linux"):
        return "Linux"
    return sys.platform


def _is_windows() -> bool:
    return sys.platform.startswith("win")


def _telegram_error_text(result: Optional[dict]) -> str:
    if not isinstance(result, dict):
        return "Unknown Telegram API error"
    if result.get("description"):
        return str(result.get("description"))
    if result.get("error"):
        raw = str(result.get("error"))
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return str(parsed.get("description") or parsed.get("message") or raw)
        except Exception:
            pass
        return raw
    return "Telegram API request failed"


def _iso_or_never(value: Optional[datetime]) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S") if isinstance(value, datetime) else "never"


def _env_or_config(name: str, default: str = "", preserved: Optional[dict[str, str]] = None) -> str:
    if preserved and name in preserved:
        return preserved[name]
    try:
        return os.environ.get(name) or config.get_str(name, default)
    except Exception:
        return os.environ.get(name, default)


def _reload_runtime_config() -> None:
    """Refresh token and safety gates after UI settings/.env changes."""
    names = (
        "TELEGRAM_BOT_TOKEN",
        "SHELL_TELEGRAM_ADMIN_CHAT_IDS",
        "SHELL_TELEGRAM_ALLOWED_CHAT_IDS",
        "SHELL_TELEGRAM_BLOCKED_CHAT_IDS",
        "SHELL_TELEGRAM_REMOTE_CONTROL_ENABLED",
        "SHELL_TELEGRAM_ALLOW_TERMINAL",
    )
    preserved = {name: os.environ[name] for name in names if name in os.environ}
    try:
        config.reload()
    except Exception:
        pass
    Config.TELEGRAM_BOT_TOKEN = _env_or_config("TELEGRAM_BOT_TOKEN", "", preserved)
    Config.ADMIN_CHAT_IDS = _parse_chat_ids(_env_or_config("SHELL_TELEGRAM_ADMIN_CHAT_IDS", "", preserved))
    Config.ALLOWED_USERS = _parse_chat_ids(_env_or_config("SHELL_TELEGRAM_ALLOWED_CHAT_IDS", "", preserved))
    Config.BLOCKED_USERS = _parse_chat_ids(_env_or_config("SHELL_TELEGRAM_BLOCKED_CHAT_IDS", "", preserved))
    Config.REMOTE_CONTROL_ENABLED = _truthy(_env_or_config("SHELL_TELEGRAM_REMOTE_CONTROL_ENABLED", "0", preserved))
    Config.ALLOW_TERMINAL = _truthy(_env_or_config("SHELL_TELEGRAM_ALLOW_TERMINAL", "0", preserved))


_reload_runtime_config()


# =============================================================================
# 🎯 DATA CLASSES
# =============================================================================

class UserRole(Enum):
    """User role levels."""
    ADMIN = "admin"
    AUTHORIZED = "authorized"
    GUEST = "guest"
    BLOCKED = "blocked"


@dataclass
class TelegramUser:
    """Telegram user profile."""
    chat_id: int
    username: str
    first_name: str
    last_name: Optional[str] = None
    role: UserRole = UserRole.GUEST
    language: str = "hinglish"
    created_at: datetime = field(default_factory=datetime.now)
    last_active: datetime = field(default_factory=datetime.now)
    message_count: int = 0
    command_count: int = 0
    preferences: Dict = field(default_factory=dict)


@dataclass
class TelegramMessage:
    """Message representation."""
    message_id: int
    chat_id: int
    user_id: int
    text: Optional[str] = None
    photo: Optional[List] = None
    document: Optional[Dict] = None
    voice: Optional[Dict] = None
    timestamp: datetime = field(default_factory=datetime.now)
    is_reply: bool = False
    reply_to_message_id: Optional[int] = None


@dataclass
class BotStatistics:
    """Bot usage statistics."""
    total_users: int = 0
    active_users_24h: int = 0
    total_messages: int = 0
    total_commands: int = 0
    ai_responses: int = 0
    pc_controls: int = 0
    uptime_seconds: float = 0.0
    errors: int = 0


@dataclass
class ScheduledMessage:
    """Scheduled message."""
    id: str
    chat_id: int
    text: str
    send_at: datetime
    created_at: datetime = field(default_factory=datetime.now)
    recurring: Optional[str] = None  # daily, weekly, monthly
    enabled: bool = True


# =============================================================================
# 🛡️ SECURITY & RATE LIMITING
# =============================================================================

class SecurityManager:
    """Manages bot security."""
    
    def __init__(self):
        self.rate_limits: Dict[int, deque] = defaultdict(deque)
        self._lock = threading.Lock()
    
    def check_rate_limit(self, chat_id: int) -> Tuple[bool, str]:
        """Checks if user exceeded rate limit."""
        with self._lock:
            now = time.time()
            
            # Clean old entries
            while (self.rate_limits[chat_id] and 
                   self.rate_limits[chat_id][0] < now - Config.RATE_LIMIT_WINDOW):
                self.rate_limits[chat_id].popleft()
            
            # Check limit
            if len(self.rate_limits[chat_id]) >= Config.RATE_LIMIT_MESSAGES_PER_MINUTE:
                wait_time = self.rate_limits[chat_id][0] + Config.RATE_LIMIT_WINDOW - now
                return False, f"⏱️ Rate limit exceeded. Wait {wait_time:.0f}s"
            
            # Record request
            self.rate_limits[chat_id].append(now)
            return True, "OK"
    
    def is_user_blocked(self, chat_id: int, user_id: Optional[int] = None) -> bool:
        """Checks if either the chat or Telegram user is blocked."""
        _reload_runtime_config()
        ids = {int(chat_id or 0)}
        if user_id is not None:
            ids.add(int(user_id or 0))
        return bool(ids & set(Config.BLOCKED_USERS))
    
    def is_user_allowed(self, chat_id: int, user_id: Optional[int] = None) -> bool:
        """Checks if the chat/user is allowed.

        Telegram private chats use the same chat_id and user_id, but groups do
        not. The UI asks for "chat IDs", so whitelist checks must accept either
        value without locking out valid group setups.
        """
        _reload_runtime_config()
        if Config.ALLOWED_USERS:
            ids = {int(chat_id or 0)}
            if user_id is not None:
                ids.add(int(user_id or 0))
            return bool(ids & set(Config.ALLOWED_USERS))
        return True  # Allow all if whitelist empty
    
    def get_user_role(self, chat_id: int, user_id: Optional[int] = None) -> UserRole:
        """Gets user role."""
        _reload_runtime_config()
        ids = {int(chat_id or 0)}
        if user_id is not None:
            ids.add(int(user_id or 0))
        if ids & set(Config.ADMIN_CHAT_IDS):
            return UserRole.ADMIN
        if ids & set(Config.BLOCKED_USERS):
            return UserRole.BLOCKED
        if ids & set(Config.ALLOWED_USERS):
            return UserRole.AUTHORIZED
        return UserRole.GUEST


# =============================================================================
# 📊 ANALYTICS
# =============================================================================

class BotAnalytics:
    """Tracks bot analytics."""
    
    def __init__(self):
        self.stats_file = Path("shell_telegram_stats.json")
        self.stats = self._load_stats()
    
    def _load_stats(self) -> Dict:
        """Loads stats from file."""
        if self.stats_file.exists():
            try:
                with open(self.stats_file, 'r') as f:
                    data = json.load(f)
                    # Ensure commands is a regular dict (defaultdict not JSON-safe)
                    if "commands" not in data or not isinstance(data["commands"], dict):
                        data["commands"] = {}
                    if "users" not in data or not isinstance(data["users"], dict):
                        data["users"] = {}
                    return data
            except Exception:
                pass  # Corrupted stats file, start fresh
        return {
            "total_users": 0,
            "total_messages": 0,
            "total_commands": 0,
            "ai_responses": 0,
            "pc_controls": 0,
            "start_time": datetime.now().isoformat(),
            "users": {},
            "commands": {},
        }
    
    def _save_stats(self):
        """Saves stats to file."""
        try:
            with open(self.stats_file, 'w') as f:
                json.dump(self.stats, f, indent=2, default=str)
        except Exception:
            pass  # Non-critical: stats save failure
    
    def log_message(self, chat_id: int, user_name: str):
        """Logs message."""
        self.stats["total_messages"] += 1

        # Convert chat_id to string for JSON compatibility
        key = str(chat_id)
        if key not in self.stats["users"]:
            self.stats["users"][key] = {
                "name": user_name,
                "messages": 0,
                "first_seen": datetime.now().isoformat(),
            }

        self.stats["users"][key]["messages"] += 1
        self.stats["users"][key]["last_seen"] = datetime.now().isoformat()

        self._save_stats()
    
    def log_command(self, command: str):
        """Logs command usage."""
        self.stats["total_commands"] += 1
        commands = self.stats.setdefault("commands", {})
        commands[command] = int(commands.get(command, 0)) + 1
        self._save_stats()
    
    def log_ai_response(self):
        """Logs AI response."""
        self.stats["ai_responses"] += 1
        self._save_stats()
    
    def log_pc_control(self):
        """Logs PC control."""
        self.stats["pc_controls"] += 1
        self._save_stats()
    
    def get_stats(self) -> BotStatistics:
        """Gets current statistics."""
        start_time = datetime.fromisoformat(self.stats["start_time"])
        uptime = (datetime.now() - start_time).total_seconds()
        
        # Count active users (24h)
        now = datetime.now()
        active_24h = 0
        for user_data in self.stats["users"].values():
            last_seen_str = user_data.get("last_seen", "")
            if not last_seen_str:
                continue
            try:
                last_seen = datetime.fromisoformat(last_seen_str)
                if now - last_seen < timedelta(hours=24):
                    active_24h += 1
            except (ValueError, TypeError):
                continue
        
        return BotStatistics(
            total_users=len(self.stats["users"]),
            active_users_24h=active_24h,
            total_messages=self.stats["total_messages"],
            total_commands=self.stats["total_commands"],
            ai_responses=self.stats["ai_responses"],
            pc_controls=self.stats["pc_controls"],
            uptime_seconds=uptime,
            errors=0
        )
    
    def get_top_users(self, limit: int = 10) -> List[Tuple[str, int]]:
        """Gets top users by message count."""
        users = [(data["name"], data["messages"]) 
                 for data in self.stats["users"].values()]
        return sorted(users, key=lambda x: x[1], reverse=True)[:limit]
    
    def get_top_commands(self, limit: int = 10) -> List[Tuple[str, int]]:
        """Gets top commands."""
        return sorted(self.stats["commands"].items(), 
                     key=lambda x: x[1], reverse=True)[:limit]


# =============================================================================
# 💾 USER MANAGER
# =============================================================================

class UserManager:
    """Manages Telegram users."""
    
    def __init__(self):
        self.users_file = Config.USERS_FILE
        self.users: Dict[int, TelegramUser] = self._load_users()
    
    def _load_users(self) -> Dict[int, TelegramUser]:
        """Loads users from file."""
        if self.users_file.exists():
            try:
                with open(self.users_file, 'r') as f:
                    data = json.load(f)
                    users = {}
                    for k, v in data.items():
                        try:
                            # Convert serialized fields back to proper types
                            if isinstance(v.get("role"), str):
                                v["role"] = UserRole(v["role"])
                            if isinstance(v.get("created_at"), str):
                                v["created_at"] = datetime.fromisoformat(v["created_at"])
                            if isinstance(v.get("last_active"), str):
                                v["last_active"] = datetime.fromisoformat(v["last_active"])
                            users[int(k)] = TelegramUser(**v)
                        except Exception:
                            continue  # Skip corrupted user entry
                    return users
            except Exception:
                pass  # Corrupted users file
        return {}
    
    def _save_users(self):
        """Saves users to file."""
        try:
            data = {
                k: asdict(v) for k, v in self.users.items()
            }
            with open(self.users_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)
        except Exception:
            pass  # Non-critical: user save failure
    
    def get_or_create_user(self, chat_id: int, username: str, 
                          first_name: str, last_name: str = None) -> TelegramUser:
        """Gets or creates user."""
        if chat_id not in self.users:
            self.users[chat_id] = TelegramUser(
                chat_id=chat_id,
                username=username or f"user_{chat_id}",
                first_name=first_name,
                last_name=last_name,
            )
            self._save_users()
        
        # Update last active
        self.users[chat_id].last_active = datetime.now()
        self._save_users()
        
        return self.users[chat_id]
    
    def set_user_role(self, chat_id: int, role: UserRole) -> bool:
        """Sets user role."""
        if chat_id not in self.users:
            return False
        
        self.users[chat_id].role = role
        self._save_users()
        return True
    
    def get_user(self, chat_id: int) -> Optional[TelegramUser]:
        """Gets user by chat ID."""
        return self.users.get(chat_id)
    
    def get_all_users(self) -> List[TelegramUser]:
        """Gets all users."""
        return list(self.users.values())
    
    def block_user(self, chat_id: int) -> bool:
        """Blocks user."""
        return self.set_user_role(chat_id, UserRole.BLOCKED)
    
    def unblock_user(self, chat_id: int) -> bool:
        """Unblocks user."""
        if chat_id in self.users:
            self.users[chat_id].role = UserRole.AUTHORIZED
            self._save_users()
            return True
        return False


# =============================================================================
# 📝 CONVERSATION MEMORY
# =============================================================================

class ConversationMemory:
    """Manages conversation history per user."""
    
    def __init__(self, max_history: int = 50):
        self.max_history = max_history
        self.histories: Dict[int, List[Dict]] = defaultdict(list)
    
    def add_message(self, chat_id: int, role: str, text: str):
        """Adds message to history."""
        self.histories[chat_id].append({
            "role": role,
            "text": text,
            "timestamp": datetime.now().isoformat()
        })
        
        # Trim if too long
        if len(self.histories[chat_id]) > self.max_history * 2:
            self.histories[chat_id] = self.histories[chat_id][-self.max_history * 2:]
    
    def get_history(self, chat_id: int, limit: int = 20) -> List[Dict]:
        """Gets conversation history."""
        return self.histories[chat_id][-limit:]
    
    def clear_history(self, chat_id: int):
        """Clears history for user."""
        self.histories[chat_id] = []
    
    def get_context_string(self, chat_id: int) -> str:
        """Gets history as context string."""
        history = self.get_history(chat_id)
        lines = []
        for entry in history:
            lines.append(f"{entry['role']}: {entry['text']}")
        return "\n".join(lines) if lines else "No prior conversation."


# =============================================================================
# 🌐 TELEGRAM API
# =============================================================================

class TelegramAPI:
    """Telegram Bot API client."""
    
    def __init__(self, token: str = None):
        self.token = str(token or Config.TELEGRAM_BOT_TOKEN or "").strip()
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.logger = logging.getLogger("telegram_api")
        self.last_error: str = ""
        self.last_status_code: Optional[int] = None
        self.last_request_at: Optional[datetime] = None
        self.last_ok_at: Optional[datetime] = None

    def _record_result(self, result: dict) -> dict:
        self.last_request_at = datetime.now()
        if result.get("ok"):
            self.last_error = ""
            self.last_status_code = None
            self.last_ok_at = self.last_request_at
        else:
            self.last_error = _telegram_error_text(result)
        return result
    
    def _sync_request(self, method: str, params: dict = None, 
                     files: dict = None) -> dict:
        """Makes synchronous API request."""
        if not self.token:
            return self._record_result({"ok": False, "error": "Telegram bot token is missing."})
        
        url = f"{self.base_url}/{method}"
        
        try:
            if files:
                # Multipart form data for files
                data = params if params else {}
                # Use urllib for file upload
                # (Simplified - in production use aiohttp or requests)
                raise NotImplementedError("File upload needs multipart handling")
            else:
                # JSON request
                if params:
                    data = json.dumps(params).encode('utf-8')
                    req = urllib.request.Request(
                        url, data=data,
                        headers={"Content-Type": "application/json"}
                    )
                else:
                    req = urllib.request.Request(url)
                
                # Dynamic timeout: Telegram long-polyling timeout + 5 seconds buffer
                req_timeout = 30
                if params and "timeout" in params:
                    try:
                        req_timeout = int(params["timeout"]) + 5
                    except (ValueError, TypeError):
                        pass
                        
                with urllib.request.urlopen(req, timeout=req_timeout) as resp:
                    return self._record_result(json.loads(resp.read().decode('utf-8')))
        
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8') if e.fp else str(e)
            self.logger.error(f"HTTP Error {e.code}: {error_body}")
            self.last_status_code = int(getattr(e, "code", 0) or 0)
            return self._record_result({"ok": False, "error": error_body})

        except urllib.error.URLError as e:
            reason = getattr(e, "reason", e)
            message = f"Network error talking to Telegram: {reason}"
            self.logger.error(message)
            return self._record_result({"ok": False, "error": message})
        
        except Exception as e:
            self.logger.error(f"API Error: {e}")
            return self._record_result({"ok": False, "error": str(e)})
    
    async def request(self, method: str, params: dict = None,
                     files: dict = None) -> dict:
        """Makes async API request."""
        return await asyncio.to_thread(self._sync_request, method, params, files)
    
    async def get_me(self) -> dict:
        """Gets bot info."""
        return await self.request("getMe")
    
    async def send_message(self, chat_id: int, text: str, 
                          parse_mode: str = "Markdown",
                          reply_markup: dict = None) -> bool:
        """Sends text message."""
        params = {
            "chat_id": chat_id,
            "text": text[:Config.MAX_MESSAGE_LENGTH],
            "parse_mode": parse_mode,
        }
        
        if reply_markup:
            params["reply_markup"] = reply_markup
        
        result = await self.request("sendMessage", params)
        
        # Fallback without parse mode
        if not result.get("ok") and parse_mode:
            params.pop("parse_mode", None)
            result = await self.request("sendMessage", params)
        
        return result.get("ok", False)
    
    async def send_photo(self, chat_id: int, photo: Union[str, bytes],
                        caption: str = None) -> bool:
        """Sends photo via multipart form upload."""
        if isinstance(photo, str) and os.path.exists(photo):
            try:
                return await asyncio.to_thread(
                    self._upload_file, "sendPhoto", chat_id, "photo", photo, caption
                )
            except Exception as e:
                self.logger.error(f"Photo send failed: {e}")
                # Fallback: send as text message
                return await self.send_message(chat_id, f"📸 Screenshot saved: {os.path.basename(photo)}")
        return False

    async def send_document(self, chat_id: int, document: str,
                           caption: str = None) -> bool:
        """Sends document via multipart form upload."""
        if os.path.exists(document):
            try:
                return await asyncio.to_thread(
                    self._upload_file, "sendDocument", chat_id, "document", document, caption
                )
            except Exception as e:
                self.logger.error(f"Document send failed: {e}")
                return await self.send_message(chat_id, f"📄 File: {os.path.basename(document)}")
        return False

    def _upload_file(self, method: str, chat_id: int, field_name: str,
                     file_path: str, caption: str = None) -> bool:
        """Uploads file via multipart form data."""
        import mimetypes
        boundary = f"----ShellBotBoundary{int(time.time())}"

        parts = []
        # chat_id field
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"chat_id\"\r\n\r\n{chat_id}")
        # caption field
        if caption:
            parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"caption\"\r\n\r\n{caption}")

        # File field
        filename = os.path.basename(file_path)
        mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"

        with open(file_path, "rb") as f:
            file_data = f.read()

        header = (
            f"--{boundary}\r\n"
            f"Content-Disposition: form-data; name=\"{field_name}\"; filename=\"{filename}\"\r\n"
            f"Content-Type: {mime_type}\r\n\r\n"
        )

        # Build body
        body = b""
        for part in parts:
            body += part.encode("utf-8") + b"\r\n"
        body += header.encode("utf-8") + file_data + b"\r\n"
        body += f"--{boundary}--\r\n".encode("utf-8")

        url = f"{self.base_url}/{method}"
        req = urllib.request.Request(
            url, data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return result.get("ok", False)
        except Exception as e:
            self.logger.error(f"File upload error: {e}")
            return False
    
    async def send_chat_action(self, chat_id: int, action: str = "typing"):
        """Sends chat action (typing, uploading_photo, etc.)."""
        return await self.request("sendChatAction", {
            "chat_id": chat_id,
            "action": action
        })
    
    async def get_updates(self, offset: int = 0, 
                         timeout: int = 30) -> List[dict]:
        """Gets updates via long polling."""
        params = {
            "timeout": timeout,
            "allowed_updates": ["message", "callback_query"]
        }
        
        if offset:
            params["offset"] = offset
        
        result = await self.request("getUpdates", params)
        
        if result.get("ok"):
            return result.get("result", [])
        
        return []
    
    async def answer_callback_query(self, callback_query_id: str,
                                   text: str = None,
                                   show_alert: bool = False):
        """Answers callback query (button press)."""
        params = {
            "callback_query_id": callback_query_id,
            "show_alert": show_alert
        }
        
        if text:
            params["text"] = text
        
        return await self.request("answerCallbackQuery", params)
    
    async def edit_message_text(self, chat_id: int, message_id: int,
                               text: str, parse_mode: str = "Markdown"):
        """Edits existing message text."""
        return await self.request("editMessageText", {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text[:Config.MAX_MESSAGE_LENGTH],
            "parse_mode": parse_mode
        })
    
    async def delete_message(self, chat_id: int, message_id: int):
        """Deletes message."""
        return await self.request("deleteMessage", {
            "chat_id": chat_id,
            "message_id": message_id
        })
    
    async def get_chat(self, chat_id: int) -> dict:
        """Gets chat info."""
        result = await self.request("getChat", {"chat_id": chat_id})
        return result.get("result", {}) if result.get("ok") else {}
    
    async def get_chat_members_count(self, chat_id: int) -> int:
        """Gets chat member count."""
        result = await self.request("getChatMembersCount", {"chat_id": chat_id})
        return result.get("result", 0) if result.get("ok") else 0
    
    async def kick_chat_member(self, chat_id: int, user_id: int):
        """Kicks member from chat (admin only)."""
        return await self.request("kickChatMember", {
            "chat_id": chat_id,
            "user_id": user_id
        })
    
    async def unban_chat_member(self, chat_id: int, user_id: int):
        """Unbans member."""
        return await self.request("unbanChatMember", {
            "chat_id": chat_id,
            "user_id": user_id
        })

    async def get_file(self, file_id: str) -> Optional[str]:
        """Gets file path from Telegram servers. Returns download URL."""
        result = await self.request("getFile", {"file_id": file_id})
        if result.get("ok"):
            file_path = result["result"].get("file_path", "")
            if file_path:
                return f"https://api.telegram.org/file/bot{self.token}/{file_path}"
        return None

    async def download_file(self, file_id: str, save_path: str) -> bool:
        """Downloads a file from Telegram to local path."""
        url = await self.get_file(file_id)
        if not url:
            return False
        try:
            def _download():
                urllib.request.urlretrieve(url, save_path)
                return True
            return await asyncio.to_thread(_download)
        except Exception as e:
            self.logger.error(f"File download error: {e}")
            return False


# =============================================================================
# 🧠 AI BRAIN (Multi-Provider)
# =============================================================================

class AIBrain:
    """Multi-provider AI brain for Telegram."""
    
    def __init__(self):
        self.providers = Config.AI_PROVIDERS
        self.logger = logging.getLogger("ai_brain")
    
    async def get_reply(self, message: str, user_name: str,
                       context: str = None,
                       tools: list = None) -> Tuple[str, str]:
        """Gets AI reply using multi-provider fallback."""
        
        # Build prompt
        system_prompt = self._build_system_prompt(user_name)
        user_prompt = self._build_user_prompt(message, context)
        
        # Try providers in order
        for provider in self.providers:
            try:
                if provider == "gemini":
                    reply = await self._ask_gemini(user_prompt, system_prompt, tools)
                elif provider == "groq":
                    reply = await self._ask_groq(user_prompt, system_prompt, tools)
                elif provider == "perplexity":
                    reply = await self._ask_perplexity(user_prompt, system_prompt)
                elif provider == "claude":
                    reply = await self._ask_claude(user_prompt, system_prompt)
                else:
                    continue
                
                if reply:
                    return reply, provider
            
            except Exception as e:
                self.logger.warning(f"{provider} failed: {e}")
                continue
        
        # Fallback
        return "Abhi busy hoon, jaldi reply karti hoon! 😊", "fallback"
    
    def _build_system_prompt(self, user_name: str) -> str:
        """Builds system prompt."""
        return f"""You are Shell OS 1.0.0, a desktop AI assistant for {user_name}.
Created by mdshoebking.
Reply in Hinglish (Hindi + English mix).
Keep responses short (1-3 sentences) for Telegram.
Use emojis naturally. Be friendly and helpful.
You can use configured tools for PC actions after permission checks.
Do not exaggerate or claim an action succeeded unless a real tool confirms it."""
    
    def _build_user_prompt(self, message: str, context: str) -> str:
        """Builds user prompt."""
        if context:
            return f"Previous conversation:\n{context}\n\nUser: {message}"
        return f"User: {message}"
    
    async def _ask_gemini(self, user_prompt: str, system_prompt: str,
                         tools: list = None) -> Optional[str]:
        """Asks Google Gemini."""
        try:
            from google import genai
            from google.genai import types
            
            api_key = config.get_str("GOOGLE_API_KEY")
            if not api_key:
                return None
            
            client = genai.Client(api_key=api_key)

            gen_config = types.GenerateContentConfig(
                temperature=Config.AI_TEMPERATURE,
                system_instruction=system_prompt,
            )

            response = await asyncio.to_thread(
                client.models.generate_content,
                model="gemini-2.5-flash",
                contents=user_prompt,
                config=gen_config,
            )
            
            if response and response.text:
                return response.text.strip()
        
        except Exception as e:
            self.logger.error(f"Gemini error: {e}")
        
        return None
    
    async def _ask_groq(self, user_prompt: str, system_prompt: str,
                       tools: list = None) -> Optional[str]:
        """Asks Groq (Llama)."""
        try:
            api_key = config.get_str("GROQ_API_KEY")
            if not api_key:
                return None
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt[-2000:]}  # Trim for rate limit
            ]
            
            payload = {
                "model": "llama-3.3-70b-versatile",
                "messages": messages,
                "temperature": Config.AI_TEMPERATURE,
                "max_tokens": Config.AI_MAX_TOKENS,
            }
            
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                "https://api.groq.com/openai/v1/chat/completions",
                data=data,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
            )
            
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode('utf-8'))
            
            if result.get("choices"):
                return result["choices"][0]["message"]["content"].strip()
        
        except Exception as e:
            self.logger.error(f"Groq error: {e}")
        
        return None
    
    async def _ask_perplexity(self, user_prompt: str, 
                             system_prompt: str) -> Optional[str]:
        """Asks Perplexity."""
        try:
            api_key = config.get_str("PERPLEXITY_API_KEY")
            if not api_key:
                return None
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            payload = json.dumps({
                "model": "sonar",
                "messages": messages,
                "temperature": Config.AI_TEMPERATURE,
                "max_tokens": 256,
            }).encode('utf-8')
            
            req = urllib.request.Request(
                "https://api.perplexity.ai/chat/completions",
                data=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
            )
            
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode('utf-8'))
            
            if result.get("choices"):
                return result["choices"][0]["message"]["content"].strip()
        
        except Exception as e:
            self.logger.error(f"Perplexity error: {e}")
        
        return None
    
    async def _ask_claude(self, user_prompt: str,
                         system_prompt: str) -> Optional[str]:
        """Asks Anthropic Claude."""
        try:
            api_key = config.get_str("ANTHROPIC_API_KEY")
            if not api_key:
                return None
            
            payload = json.dumps({
                "model": "claude-sonnet-4-20250514",
                "max_tokens": Config.AI_MAX_TOKENS,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}]
            }).encode('utf-8')
            
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=payload,
                headers={
                    "x-api-key": api_key,
                    "Content-Type": "application/json",
                    "anthropic-version": "2023-06-01"
                }
            )
            
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode('utf-8'))
            
            if result.get("content"):
                return result["content"][0]["text"].strip()
        
        except Exception as e:
            self.logger.error(f"Claude error: {e}")
        
        return None


# =============================================================================
# 🤖 MAIN BOT
# =============================================================================

class ShellTelegramBot:
    """Main Telegram bot class."""
    
    def __init__(self):
        self.api: Optional[TelegramAPI] = None
        self.security = SecurityManager()
        self.analytics = BotAnalytics()
        self.users = UserManager()
        self.memory = ConversationMemory()
        self.ai = AIBrain()
        
        self.active = False
        self.task = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.thread: Optional[threading.Thread] = None
        self.last_update_id = 0
        self.authorized_chat_id = None
        self.start_time = None
        self.bot_info: Dict[str, Any] = {}
        self.last_error: str = ""
        self.last_poll_at: Optional[datetime] = None
        self.last_update_at: Optional[datetime] = None
        
        self.logger = logging.getLogger("shell_telegram_bot")

    def _task_running(self) -> bool:
        if self.thread and self.thread.is_alive() and self.active:
            return True
        return bool(self.task and not self.task.done() and self.active)

    def _set_error(self, message: str) -> None:
        self.last_error = str(message or "").strip()

    def _run_polling_thread(self) -> None:
        """Run polling on a durable loop independent of UI/tool worker loops."""
        loop = asyncio.new_event_loop()
        self.loop = loop
        try:
            asyncio.set_event_loop(loop)
            self.task = loop.create_task(self._polling_loop())
            loop.run_until_complete(self.task)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            self._set_error(str(exc))
            self.logger.error("Telegram polling thread crashed: %s", exc)
        finally:
            self.active = False
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                try:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                except Exception:
                    pass
            loop.close()

    async def _send_platform_unsupported(self, chat_id: int, feature: str) -> str:
        msg = (
            f"⚠️ {feature} is not available on {_platform_label()} from Telegram yet. "
            "Windows PC control remains supported when Shell is running on Windows."
        )
        await self.api.send_message(chat_id, msg)
        return msg

    def _remote_control_allowed(self, chat_id: int, user_id: int) -> Tuple[bool, str]:
        """Gate real PC-control actions behind explicit UI settings."""
        _reload_runtime_config()
        if not Config.REMOTE_CONTROL_ENABLED:
            return (
                False,
                "🔒 Telegram PC control is OFF. Enable it in Shell Settings > API Keys > Telegram Remote Control.",
            )
        allowed = set(Config.ALLOWED_USERS) | set(Config.ADMIN_CHAT_IDS)
        if not allowed:
            return (
                False,
                f"🔒 Add your Telegram chat ID first, then retry. This chat ID is `{chat_id}`.",
            )
        if chat_id not in allowed and user_id not in allowed:
            return (
                False,
                f"⛔ This Telegram account is not allowed to control this PC. Add chat ID `{chat_id}` in Shell Settings.",
            )
        return True, "OK"

    def _terminal_allowed(self) -> bool:
        _reload_runtime_config()
        return bool(Config.ALLOW_TERMINAL)
    
    async def start(self) -> str:
        """Starts the bot."""
        _reload_runtime_config()
        if self.active and self._task_running():
            return "⚠️ Bot pehle se chal raha hai!"
        if self.active and not self._task_running():
            self.active = False
            self._set_error("Previous Telegram polling task stopped unexpectedly.")
        
        if not Config.TELEGRAM_BOT_TOKEN:
            return "❌ Token nahi hai! Pehle token set karo."
        if not _telegram_token_shape_ok(Config.TELEGRAM_BOT_TOKEN):
            self._set_error("Telegram token format is invalid.")
            return "❌ Telegram token format invalid hai. @BotFather se full bot token paste karo."
        
        self.api = TelegramAPI(Config.TELEGRAM_BOT_TOKEN)
        
        # Test connection
        result = await self.api.get_me()
        if not result.get("ok"):
            self._set_error(_telegram_error_text(result))
            return f"❌ Telegram connection failed: {self.last_error}"
        
        bot_info = result.get("result", {})
        self.bot_info = bot_info
        self._set_error("")
        
        self.active = True
        self.start_time = datetime.now()
        self.thread = threading.Thread(
            target=self._run_polling_thread,
            name="ShellTelegramPolling",
            daemon=True,
        )
        self.thread.start()
        
        return (
            f"✅ *Telegram Bot STARTED!* 🚀\n\n"
            f"🤖 Bot: @{bot_info.get('username', '?')}\n"
            f"📱 Name: {bot_info.get('first_name', 'Shell AI')}\n"
            f"🛠️ Project: Shell OS 1.0.0 by mdshoebking\n\n"
            f"*Commands:*\n"
            f"/start - Start bot\n"
            f"/help - All commands\n"
            f"/status - Bot status\n"
            f"/pc_status - PC health\n"
            f"/screenshot - Take screenshot\n\n"
            f"Phone se /start bhejo. Shell aapka chat ID reply karega.\n"
            f"Ya seedha baat karo! 😊"
        )
    
    async def stop(self) -> str:
        """Stops the bot."""
        if not self.active:
            return "⚠️ Bot chal nahi raha tha."
        
        self.active = False
        
        if self.loop and self.loop.is_running() and self.task and not self.task.done():
            try:
                self.loop.call_soon_threadsafe(self.task.cancel)
            except Exception as _e:
                logger.debug("telegram polling cancel skipped: %s", _e)
        if self.thread and self.thread.is_alive():
            await asyncio.to_thread(self.thread.join, 5)
        self.task = None
        self.thread = None
        return "🛑 Telegram Bot stopped."
    
    async def _polling_loop(self):
        """Main polling loop with retry and connection recovery."""
        self.logger.info("🤖 Telegram Bot polling started!")
        consecutive_errors = 0
        max_consecutive_errors = 10

        while self.active:
            try:
                if not self.api:
                    raise RuntimeError("Telegram API client is not initialized.")
                result = await self.api.request("getUpdates", {
                    "offset": self.last_update_id + 1,
                    "timeout": 30,
                    "allowed_updates": ["message", "callback_query"],
                })
                self.last_poll_at = datetime.now()
                if not result.get("ok"):
                    raise RuntimeError(_telegram_error_text(result))
                updates = result.get("result", [])

                # Reset error counter on success
                consecutive_errors = 0
                self._set_error("")

                for update in updates:
                    self.last_update_id = update.get("update_id", 0)
                    self.last_update_at = datetime.now()

                    # Handle message
                    if "message" in update:
                        try:
                            await self._handle_message(update["message"])
                        except Exception as msg_err:
                            self.logger.error(f"Message handler error: {msg_err}")

                    # Handle callback query (button press)
                    elif "callback_query" in update:
                        try:
                            await self._handle_callback(update["callback_query"])
                        except Exception as cb_err:
                            self.logger.error(f"Callback handler error: {cb_err}")

                # Small delay between polls
                await asyncio.sleep(0.5)

            except asyncio.CancelledError:
                break

            except Exception as e:
                consecutive_errors += 1
                self._set_error(str(e))
                self.logger.error(f"Polling error ({consecutive_errors}/{max_consecutive_errors}): {e}")

                if consecutive_errors >= max_consecutive_errors:
                    self.logger.error("Too many consecutive errors - stopping bot")
                    self.active = False
                    break

                # Exponential backoff: 2s, 4s, 8s, ... max 30s
                wait_time = min(2 ** consecutive_errors, 30)
                await asyncio.sleep(wait_time)

        self.active = False
        self.logger.info("🛑 Telegram Bot polling stopped.")
    
    async def _smart_execute(self, chat_id: int, user_id: int, user_name: str, text: str) -> str:
        """Smart NLP router: detects user intent and executes PC tools directly.

        Uses Gemini function calling to understand natural language commands
        like 'chrome open kar', 'screenshot de', 'volume kam kar' etc.
        and executes them directly instead of just chatting.
        """
        try:
            from google import genai
            from google.genai import types

            api_key = config.get_str("GOOGLE_API_KEY")
            if not api_key:
                # No Gemini key, fall back to simple AI chat
                return await self._fallback_chat(chat_id, user_name, text)

            # Define available tools for Gemini function calling
            _S = types.Schema
            _FD = types.FunctionDeclaration
            tool_definitions = types.Tool(function_declarations=[
                _FD(name="open_app",
                    description="Open an application on PC. Use for: 'chrome open karo', 'notepad kholo', 'calculator start karo', 'browser open kar', 'file manager khol', etc.",
                    parameters=_S(type="OBJECT", properties={"app_name": _S(type="STRING", description="App name like chrome, notepad, calculator, cmd, explorer, vlc, vscode, etc.")}, required=["app_name"])),
                _FD(name="close_app",
                    description="Close/kill an application. Use for: 'chrome band karo', 'notepad close karo', 'app band kar', etc.",
                    parameters=_S(type="OBJECT", properties={"app_name": _S(type="STRING", description="Process name like chrome, notepad, firefox, etc.")}, required=["app_name"])),
                _FD(name="take_screenshot",
                    description="Take a screenshot of PC screen. Use for: 'screenshot lo', 'screen dikhao', 'kya chal raha hai PC pe', 'screen capture', etc.",
                    parameters=_S(type="OBJECT", properties={})),
                _FD(name="google_search",
                    description="Search Google for information. Use for: 'search karo', 'Google pe dhundho', 'find karo', 'look up', etc.",
                    parameters=_S(type="OBJECT", properties={"query": _S(type="STRING", description="Search query")}, required=["query"])),
                _FD(name="run_command",
                    description="Run a terminal/cmd command on PC. Use for: 'ipconfig dikhao', 'dir karo', 'ping karo', 'wifi password', 'command chalao', system commands, etc.",
                    parameters=_S(type="OBJECT", properties={"command": _S(type="STRING", description="Terminal command to execute")}, required=["command"])),
                _FD(name="control_volume",
                    description="Control PC volume/sound. Use for: 'volume badhao', 'awaaz kam karo', 'mute karo', 'volume 50', 'sound off', etc.",
                    parameters=_S(type="OBJECT", properties={"action": _S(type="STRING", description="up, down, mute, unmute, or a number 0-100")}, required=["action"])),
                _FD(name="type_text",
                    description="Type text on PC keyboard. Use for: 'likh do', 'type karo', 'keyboard se likho', etc.",
                    parameters=_S(type="OBJECT", properties={"text": _S(type="STRING", description="Text to type")}, required=["text"])),
                _FD(name="pc_status",
                    description="Get PC system status (CPU, RAM, disk, battery). Use for: 'PC kaisa hai', 'system status', 'RAM kitni hai', 'CPU usage', 'battery', etc.",
                    parameters=_S(type="OBJECT", properties={})),
                _FD(name="list_apps",
                    description="List running applications/processes. Use for: 'kya chal raha hai', 'running apps', 'konse app open hain', 'task list', etc.",
                    parameters=_S(type="OBJECT", properties={})),
                _FD(name="network_info",
                    description="Get network/internet/WiFi info. Use for: 'internet speed', 'wifi info', 'IP address', 'network status', 'connected hai?', etc.",
                    parameters=_S(type="OBJECT", properties={})),
                _FD(name="disk_info",
                    description="Get disk/storage space info. Use for: 'disk space', 'storage kitna hai', 'C drive', 'free space', etc.",
                    parameters=_S(type="OBJECT", properties={})),
                _FD(name="lock_pc",
                    description="Lock the PC screen. Use for: 'PC lock karo', 'screen lock', 'lock kar do', etc.",
                    parameters=_S(type="OBJECT", properties={})),
                _FD(name="play_media",
                    description="Play a YouTube video or media file. Use for: 'gaana bajao', 'video chala', 'YouTube pe play karo', 'music sun', etc.",
                    parameters=_S(type="OBJECT", properties={"query": _S(type="STRING", description="Song/video name or URL")}, required=["query"])),
                _FD(name="set_brightness",
                    description="Set screen brightness. Use for: 'brightness badhao', 'screen dim karo', 'brightness 50', etc.",
                    parameters=_S(type="OBJECT", properties={"level": _S(type="STRING", description="Brightness level 0-100 or up/down")}, required=["level"])),
                _FD(name="quick_actions_menu",
                    description="Show quick action buttons panel. Use for: 'menu dikhao', 'kya kar sakte ho', 'options dikhao', 'controls', etc.",
                    parameters=_S(type="OBJECT", properties={})),
                _FD(name="chat_reply",
                    description="Normal conversation reply. Use ONLY when user is chatting, greeting, joking, asking general knowledge questions — NOT asking to do anything on PC.",
                    parameters=_S(type="OBJECT", properties={"reply": _S(type="STRING", description="Reply in Hinglish, short and friendly with emojis")}, required=["reply"])),
            ])

            client = genai.Client(api_key=api_key)

            system_prompt = (
                f"You are Shell OS 1.0.0 assistant for {user_name}, created by mdshoebking. "
                "Analyze the user message and decide which tool to call. "
                "If user wants to do something on PC (open app, close app, search, screenshot, command, volume, type, status), "
                "call the appropriate tool. If user is just chatting normally, call chat_reply with a Hinglish response. "
                "ALWAYS call exactly one tool."
            )

            gen_config = types.GenerateContentConfig(
                temperature=0.3,
                system_instruction=system_prompt,
                tools=[tool_definitions],
            )

            response = await asyncio.to_thread(
                client.models.generate_content,
                model="gemini-2.5-flash",
                contents=text,
                config=gen_config,
            )

            # Process function call
            if response and response.candidates:
                candidate = response.candidates[0]
                if candidate.content and candidate.content.parts:
                    for part in candidate.content.parts:
                        if hasattr(part, 'function_call') and part.function_call:
                            fc = part.function_call
                            fn_name = fc.name
                            fn_args = dict(fc.args) if fc.args else {}
                            return await self._execute_tool(chat_id, user_id, fn_name, fn_args)
                        elif hasattr(part, 'text') and part.text:
                            # Gemini responded with text instead of function call
                            await self.api.send_message(chat_id, part.text.strip())
                            return part.text.strip()

        except Exception as e:
            self.logger.warning(f"Smart execute failed: {e}")

        # Fallback to simple AI chat
        return await self._fallback_chat(chat_id, user_name, text)

    async def _execute_tool(self, chat_id: int, user_id: int, tool_name: str, args: dict) -> str:
        """Executes a tool and sends result to Telegram."""
        import re

        try:
            pc_tools = {
                "open_app", "close_app", "take_screenshot", "google_search",
                "run_command", "control_volume", "type_text", "pc_status",
                "list_apps", "network_info", "disk_info", "lock_pc",
                "play_media", "set_brightness", "quick_actions_menu",
            }
            if tool_name in pc_tools:
                ok, msg = self._remote_control_allowed(chat_id, user_id)
                if not ok:
                    await self.api.send_message(chat_id, msg)
                    return msg
            if tool_name == "run_command" and not self._terminal_allowed():
                msg = "🚫 Telegram terminal execution is OFF. Enable Telegram terminal access only when you really need it."
                await self.api.send_message(chat_id, msg)
                return msg

            if tool_name == "open_app":
                app = args.get("app_name", "")
                await self._cmd_open(chat_id, user_id, app)
                return f"Open app requested: {app}"

            elif tool_name == "close_app":
                app = args.get("app_name", "")
                await self._cmd_close(chat_id, user_id, app)
                return f"Close app requested: {app}"

            elif tool_name == "take_screenshot":
                await self._cmd_screenshot(chat_id, user_id)
                return "Screenshot sent"

            elif tool_name == "google_search":
                query = args.get("query", "")
                if not query:
                    await self.api.send_message(chat_id, "❌ Search query chahiye!")
                    return "No query"
                import webbrowser
                url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
                webbrowser.open(url)
                msg = f"🔍 Searching: *{query}*"
                await self.api.send_message(chat_id, msg)
                self.analytics.log_pc_control()
                return msg

            elif tool_name == "run_command":
                cmd = args.get("command", "")
                if not cmd:
                    await self.api.send_message(chat_id, "❌ Command chahiye!")
                    return "No command"
                await self._cmd_terminal(chat_id, user_id, cmd)
                return f"Command executed: {cmd}"

            elif tool_name == "control_volume":
                action = args.get("action", "")
                await self._cmd_volume(chat_id, user_id, action)
                return f"Volume: {action}"

            elif tool_name == "type_text":
                txt = args.get("text", "")
                await self._cmd_type(chat_id, user_id, txt)
                return f"Typed: {txt}"

            elif tool_name == "pc_status":
                await self._cmd_pc_status(chat_id, user_id)
                return "PC status sent"

            elif tool_name == "list_apps":
                await self._cmd_apps(chat_id, user_id)
                return "Apps list sent"

            elif tool_name == "network_info":
                await self._cmd_network_info(chat_id, user_id)
                return "Network info sent"

            elif tool_name == "disk_info":
                try:
                    import psutil
                    partitions = psutil.disk_partitions()
                    disk_text = "💾 *Disk Info:*\n"
                    for p in partitions:
                        try:
                            usage = psutil.disk_usage(p.mountpoint)
                            total_gb = usage.total / (1024**3)
                            used_gb = usage.used / (1024**3)
                            free_gb = usage.free / (1024**3)
                            disk_text += (
                                f"\n*{p.device}*\n"
                                f"  Total: {total_gb:.1f} GB\n"
                                f"  Used: {used_gb:.1f} GB ({usage.percent}%)\n"
                                f"  Free: {free_gb:.1f} GB\n"
                            )
                        except PermissionError as _e:
                            logger.debug("ignored PermissionError: %s", _e)
                    await self.api.send_message(chat_id, disk_text)
                    self.analytics.log_pc_control()
                except ImportError:
                    await self.api.send_message(chat_id, "⚠️ psutil not installed")
                return "Disk info sent"

            elif tool_name == "lock_pc":
                await self._cmd_lock_pc(chat_id, user_id)
                return "PC locked"

            elif tool_name == "play_media":
                query = args.get("query", "")
                if not query:
                    await self.api.send_message(chat_id, "❌ Kya play karna hai?")
                    return "No query"
                import webbrowser
                yt_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
                webbrowser.open(yt_url)
                msg = f"🎵 Playing: *{query}*"
                await self.api.send_message(chat_id, msg)
                self.analytics.log_pc_control()
                return msg

            elif tool_name == "set_brightness":
                level = args.get("level", "")
                await self._cmd_brightness(chat_id, user_id, level)
                return f"Brightness set to {level}"

            elif tool_name == "quick_actions_menu":
                await self._send_quick_actions(chat_id)
                return "Quick actions menu sent"

            elif tool_name == "chat_reply":
                reply = args.get("reply", "")
                if reply:
                    await self.api.send_message(chat_id, reply)
                    return reply
                return ""

            else:
                await self.api.send_message(chat_id, f"⚠️ Unknown tool: {tool_name}")
                return f"Unknown tool: {tool_name}"

        except Exception as e:
            self.logger.error(f"Tool execution error ({tool_name}): {e}")
            await self.api.send_message(chat_id, f"❌ Error executing {tool_name}: {e}")
            return f"Error: {e}"

    async def _fallback_chat(self, chat_id: int, user_name: str, text: str) -> str:
        """Fallback to simple AI chat when smart execute unavailable."""
        context = self.memory.get_context_string(chat_id)
        reply, provider = await self.ai.get_reply(text, user_name, context)
        await self.api.send_message(chat_id, reply)
        return reply

    async def _handle_message(self, message: dict):
        """Handles incoming message."""
        try:
            chat_id = message.get("chat", {}).get("id", 0)
            user = message.get("from", {})
            user_id = user.get("id", 0)
            user_name = user.get("first_name", "User")
            text = message.get("text", "")
            
            if not chat_id:
                return

            # Check for voice message
            voice = message.get("voice") or message.get("audio")
            photo = message.get("photo")
            caption = message.get("caption", "")

            # Need at least text, voice, or photo
            if not text and not voice and not photo:
                return

            # Check security
            if self.security.is_user_blocked(chat_id, user_id):
                return

            if not self.security.is_user_allowed(chat_id, user_id):
                await self.api.send_message(
                    chat_id,
                    f"⛔ Access denied. Add this Telegram chat ID in Shell Settings: `{chat_id}`"
                )
                return

            # Rate limit check
            allowed, msg = self.security.check_rate_limit(chat_id)
            if not allowed:
                await self.api.send_message(chat_id, msg)
                return

            # Get or create user
            telegram_user = self.users.get_or_create_user(
                user_id,
                user.get("username"),
                user_name,
                user.get("last_name")
            )
            telegram_user.role = self.security.get_user_role(chat_id, user_id)

            telegram_user.message_count += 1

            # Log message
            self.analytics.log_message(chat_id, user_name)

            # Auto-authorize first user
            if self.authorized_chat_id is None:
                self.authorized_chat_id = chat_id
                await self.api.send_message(
                    chat_id,
                    f"✅ *Welcome {user_name}!* 🎉\n\n"
                    f"Ab aap Shell OS 1.0.0 se Telegram pe baat kar sakte ho.\n"
                    f"Project mdshoebking ne banaya hai.\n\n"
                    f"🆔 Aapka chat ID: `{chat_id}`\n"
                    f"PC control ke liye is ID ko Shell Settings > Telegram mein add karo.\n\n"
                    f"🎤 Voice bhi bhej sakte ho!\n"
                    f"📸 Photo bhi bhej sakte ho!\n\n"
                    f"/help - All commands dekhne ke liye"
                )

            # Handle voice message
            if voice:
                await self._handle_voice(chat_id, user_id, user_name, voice)
                self.analytics.log_ai_response()
                return

            # Handle photo message
            if photo:
                await self._handle_photo(chat_id, user_id, user_name, photo, caption)
                self.analytics.log_ai_response()
                return

            # Text message handling
            if not text:
                return

            # Show typing action
            await self.api.send_chat_action(chat_id, "typing")

            # Check if command
            if text.startswith("/"):
                await self._handle_command(chat_id, user_id, text)
            else:
                # Smart routing: try tool execution first, fallback to chat
                reply = await self._smart_execute(chat_id, user_id, user_name, text)

                # Save to memory
                self.memory.add_message(chat_id, user_name, text)
                self.memory.add_message(chat_id, "Shell", reply)
                self.analytics.log_ai_response()
        
        except Exception as e:
            self.logger.error(f"Message handling error: {e}")
    
    async def _handle_command(self, chat_id: int, user_id: int, text: str):
        """Handles command."""
        try:
            parts = text.split(maxsplit=1)
            command = parts[0].lower()
            args = parts[1] if len(parts) > 1 else ""
            
            self.analytics.log_command(command)
            pc_commands = {
                "/pc_status", "/screenshot", "/apps", "/search", "/open",
                "/close", "/cmd", "/volume", "/type", "/quick", "/network",
                "/disk", "/lock",
            }
            if command in pc_commands:
                ok, msg = self._remote_control_allowed(chat_id, user_id)
                if not ok:
                    await self.api.send_message(chat_id, msg)
                    return
            if command == "/cmd" and not self._terminal_allowed():
                await self.api.send_message(
                    chat_id,
                    "🚫 Telegram terminal execution is OFF. Enable it from Shell Settings only for trusted sessions.",
                )
                return
            
            # Command handlers
            if command == "/start":
                await self._cmd_start(chat_id, user_id)
            
            elif command == "/help":
                await self._cmd_help(chat_id, user_id)
            
            elif command == "/status":
                await self._cmd_status(chat_id, user_id)
            
            elif command == "/pc_status":
                await self._cmd_pc_status(chat_id, user_id)
            
            elif command == "/screenshot":
                await self._cmd_screenshot(chat_id, user_id)
            
            elif command == "/apps":
                await self._cmd_apps(chat_id, user_id)

            elif command == "/network":
                await self._cmd_network_info(chat_id, user_id)

            elif command == "/disk":
                await self._execute_tool(chat_id, user_id, "disk_info", {})

            elif command == "/lock":
                await self._cmd_lock_pc(chat_id, user_id)
            
            elif command == "/search":
                await self._cmd_search(chat_id, user_id, args)
            
            elif command == "/open":
                await self._cmd_open(chat_id, user_id, args)
            
            elif command == "/close":
                await self._cmd_close(chat_id, user_id, args)
            
            elif command == "/cmd":
                await self._cmd_terminal(chat_id, user_id, args)
            
            elif command == "/volume":
                await self._cmd_volume(chat_id, user_id, args)
            
            elif command == "/type":
                await self._cmd_type(chat_id, user_id, args)
            
            elif command == "/quick":
                await self._send_quick_actions(chat_id)

            elif command == "/stats":
                await self._cmd_stats(chat_id, user_id)

            elif command == "/users":
                await self._cmd_users(chat_id, user_id)

            else:
                await self.api.send_message(
                    chat_id,
                    f"❓ Unknown command: {command}\n\n/help for list"
                )
        
        except Exception as e:
            self.logger.error(f"Command handling error: {e}")
    
    # Command Handlers
    async def _cmd_start(self, chat_id: int, user_id: int):
        """Handle /start command."""
        user = self.users.get_user(user_id)
        name = user.first_name if user else "User"
        
        await self.api.send_message(
            chat_id,
            f"👋 *Welcome {name}!* 🎉\n\n"
            f"Main hoon Shell OS 1.0.0 - aapka desktop AI assistant.\n"
            f"Project mdshoebking ne banaya hai.\n\n"
            f"🆔 Aapka chat ID: `{chat_id}`\n"
            f"Is ID ko Shell Settings > Telegram mein allow karo for PC control.\n\n"
            f"*Kya kar sakti hoon:*\n"
            f"💬 Normal baat-cheet\n"
            f"💻 PC control remotely\n"
            f"🔍 Google search\n"
            f"📸 Screenshot\n"
            f"📊 System status\n\n"
            f"/help - All commands"
        )
    
    async def _cmd_help(self, chat_id: int, user_id: int):
        """Handle /help command."""
        help_text = """
🤖 *Shell AI Telegram Commands*

🧠 *Smart Mode:*
Seedha Hinglish mein bolo — Shell samajh ke execute karega!
• "chrome open karo"
• "screenshot de"
• "volume badhao"
• "PC ka status batao"
• "disk space kitna hai"
• "network info do"
• "PC lock karo"
• "gaana bajao"

🎤 *Voice:* Voice message bhejo — Shell sunega aur execute karega!
📸 *Photo:* Photo bhejo — Shell describe karega!

💻 *Commands:*
/open <app> - Open app
/close <app> - Close app
/cmd <command> - Terminal command
/search <query> - Google search
/screenshot - Take screenshot
/pc_status - PC health check
/apps - Running apps
/network - Network info
/disk - Disk/storage info
/lock - Lock workstation
/volume <up/down/mute/0-100> - Volume
/type <text> - Type text
/quick - Quick action buttons

🔐 PC-control commands require Shell Settings > Telegram Remote Control:
enable PC control and add your Telegram chat ID first.
Use /start to see your chat ID.

📊 *Bot Info:*
/status - Bot status
/stats - Usage statistics
/users - User list (admin)
"""
        await self.api.send_message(chat_id, help_text)
    
    async def _cmd_status(self, chat_id: int, user_id: int):
        """Handle /status command."""
        stats = self.analytics.get_stats()
        
        uptime_hours = stats.uptime_seconds / 3600
        
        status = f"""
📊 *Bot Status*

✅ Status: Active
🖥️ Platform: {_platform_label()}
🆔 This chat ID: `{chat_id}`
🔐 PC control: {'ON' if Config.REMOTE_CONTROL_ENABLED else 'OFF'}
⌨️ Terminal: {'ON' if Config.ALLOW_TERMINAL else 'OFF'}
⏱️ Uptime: {uptime_hours:.1f} hours
👥 Users: {stats.total_users}
📨 Messages: {stats.total_messages}
🔧 Commands: {stats.total_commands}
🤖 AI Responses: {stats.ai_responses}
💻 PC Controls: {stats.pc_controls}
⚠️ Last error: {self.last_error or 'none'}
"""
        await self.api.send_message(chat_id, status)
    
    async def _cmd_pc_status(self, chat_id: int, user_id: int):
        """Handle /pc_status command."""
        try:
            import psutil
            
            cpu = psutil.cpu_percent(interval=1)
            ram = psutil.virtual_memory()
            battery = psutil.sensors_battery()
            
            bat_str = "N/A"
            if battery:
                icon = "🔌" if battery.power_plugged else "🔋"
                bat_str = f"{battery.percent}% {icon}"
            
            status = f"""
🖥️ *PC Status*

• CPU: {cpu}%
• RAM: {ram.percent}% ({ram.used // (1024**3)}/{ram.total // (1024**3)} GB)
• Battery: {bat_str}
• Time: {datetime.now().strftime('%I:%M %p')}
"""
            await self.api.send_message(chat_id, status)
        
        except ImportError:
            await self.api.send_message(chat_id, "⚠️ psutil not installed")
    
    async def _cmd_screenshot(self, chat_id: int, user_id: int):
        """Handle /screenshot command."""
        try:
            import pyautogui

            ss_dir = os.path.join(os.path.expanduser("~"), "Desktop")
            os.makedirs(ss_dir, exist_ok=True)
            ss_path = os.path.join(
                ss_dir,
                f"shell_ss_{datetime.now().strftime('%H%M%S')}.png"
            )

            screenshot = pyautogui.screenshot()
            screenshot.save(ss_path)

            # Send the actual photo file
            sent = await self.api.send_photo(chat_id, ss_path, caption="📸 Screenshot from Shell AI")
            if not sent:
                await self.api.send_message(chat_id, f"📸 Screenshot saved: {ss_path}")

            self.analytics.log_pc_control()

        except Exception as e:
            await self.api.send_message(chat_id, f"❌ Screenshot failed: {e}")
    
    async def _cmd_apps(self, chat_id: int, user_id: int):
        """Handle /apps command."""
        try:
            apps = []
            try:
                import psutil

                seen = set()
                for proc in psutil.process_iter(["name", "pid"]):
                    name = (proc.info.get("name") or "").strip()
                    if not name or name.lower() in seen:
                        continue
                    seen.add(name.lower())
                    apps.append(f"• {name}")
                    if len(apps) >= 20:
                        break
            except Exception:
                if _is_windows():
                    tasklist = subprocess.run(
                        ["tasklist", "/FO", "CSV", "/NH"],
                        capture_output=True, text=True, timeout=10
                    )
                    lines = tasklist.stdout.strip().split("\n")[:20]
                    for line in lines:
                        parts = line.split(",")
                        if parts:
                            apps.append(f"• {parts[0].strip(chr(34))}")
                else:
                    result = subprocess.run(
                        ["ps", "-axo", "comm="],
                        capture_output=True, text=True, timeout=10
                    )
                    for line in result.stdout.splitlines()[:20]:
                        name = os.path.basename(line.strip())
                        if name:
                            apps.append(f"• {name}")
            
            await self.api.send_message(
                chat_id,
                "📱 *Running Apps:*\n" + ("\n".join(apps) if apps else "No visible processes found.")
            )
            self.analytics.log_pc_control()
        
        except Exception as e:
            await self.api.send_message(chat_id, f"❌ Error: {e}")
    
    async def _cmd_search(self, chat_id: int, user_id: int, query: str):
        """Handle /search command."""
        if not query:
            await self.api.send_message(chat_id, "❌ Query chahiye! `/search <query>`")
            return
        
        import webbrowser
        url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
        webbrowser.open(url)
        
        await self.api.send_message(
            chat_id,
            f"✅ Searching: `{query}`"
        )
    
    async def _cmd_open(self, chat_id: int, user_id: int, app: str):
        """Handle /open command."""
        if not app:
            await self.api.send_message(chat_id, "❌ App name chahiye!")
            return
        
        # Sanitize: only allow simple app names (no paths, no special chars)
        import re
        if not re.match(r'^[a-zA-Z0-9_\-\. ]+$', app):
            await self.api.send_message(chat_id, "❌ Invalid app name. Only letters, numbers, spaces allowed.")
            return
        
        try:
            if _is_windows():
                subprocess.Popen(["cmd", "/c", "start", "", app])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-a", app])
            else:
                subprocess.Popen([app])
            await self.api.send_message(chat_id, f"✅ Opening: {app}")
            self.analytics.log_pc_control()
        except Exception as e:
            await self.api.send_message(chat_id, f"❌ Error: {e}")
    
    async def _cmd_close(self, chat_id: int, user_id: int, app: str):
        """Handle /close command."""
        if not app:
            await self.api.send_message(chat_id, "❌ App name chahiye!")
            return
        
        # Sanitize: only allow process names
        import re
        if not re.match(r'^[a-zA-Z0-9_\-\. ]+$', app):
            await self.api.send_message(chat_id, "❌ Invalid process name.")
            return
        
        try:
            target = app
            if _is_windows():
                if not target.lower().endswith(".exe"):
                    target += ".exe"
                subprocess.run(["taskkill", "/IM", target, "/F"], capture_output=True, timeout=10)
            else:
                subprocess.run(["pkill", "-x", target], capture_output=True, timeout=10)
            await self.api.send_message(chat_id, f"✅ Closed: {target}")
            self.analytics.log_pc_control()
        except Exception as e:
            await self.api.send_message(chat_id, f"❌ Close failed: {e}")
    
    async def _cmd_terminal(self, chat_id: int, user_id: int, cmd: str):
        """Handle /cmd command."""
        if not cmd:
            await self.api.send_message(chat_id, "❌ Command chahiye!")
            return
        if not self._terminal_allowed():
            await self.api.send_message(
                chat_id,
                "🚫 Telegram terminal execution is OFF. Enable Telegram terminal access only for trusted sessions.",
            )
            return
        
        # Block dangerous commands
        import re
        dangerous = re.compile(r'(format\s|del\s/|rmdir\s/s|rd\s/s|shutdown|rm\s-rf|mkfs|dd\sif=)', re.IGNORECASE)
        if dangerous.search(cmd):
            await self.api.send_message(chat_id, "🚫 Command blocked by safety filter.")
            return
        
        try:
            runner = ["cmd", "/c", cmd] if _is_windows() else [os.environ.get("SHELL", "/bin/sh"), "-lc", cmd]
            result = subprocess.run(
                runner, capture_output=True, text=True,
                timeout=15, cwd=os.path.expanduser("~")
            )
            
            output = result.stdout[:1000] if result.stdout else ""
            error = result.stderr[:500] if result.stderr else ""
            
            if output:
                await self.api.send_message(
                    chat_id,
                    f"✅ Command executed:\n```\n{output}\n```"
                )
            elif error:
                await self.api.send_message(
                    chat_id,
                    f"⚠️ Error:\n```\n{error}\n```"
                )
            else:
                await self.api.send_message(chat_id, "✅ Command executed (no output)")
        
        except Exception as e:
            await self.api.send_message(chat_id, f"❌ Error: {e}")
    
    async def _cmd_volume(self, chat_id: int, user_id: int, action: str):
        """Handle /volume command."""
        if not action:
            await self.api.send_message(
                chat_id,
                "❌ Usage: `/volume <up/down/mute/0-100>`"
            )
            return
        
        try:
            from keyboard_mouse_CTRL import control_volume_tool
            result = await control_volume_tool(action)
            await self.api.send_message(chat_id, f"✅ Volume: {result}")
        except Exception as e:
            await self.api.send_message(chat_id, f"❌ Error: {e}")
    
    async def _cmd_network_info(self, chat_id: int, user_id: int):
        """Handle network information across platforms."""
        try:
            if _is_windows():
                command = ["cmd", "/c", "ipconfig"]
            elif sys.platform == "darwin":
                command = ["ifconfig"]
            else:
                command = ["sh", "-lc", "ip addr 2>/dev/null || ifconfig 2>/dev/null"]
            result = subprocess.run(command, capture_output=True, text=True, timeout=10)
            output = (result.stdout or result.stderr or "No output")[:1800]
            lines = []
            for line in output.splitlines():
                clean = line.strip()
                low = clean.lower()
                if any(k in low for k in ["ipv4", "inet ", "gateway", "dns", "adapter", "broadcast", "ether"]):
                    lines.append(f"• {clean}")
            info = "\n".join(lines[:18]) if lines else output[:900]
            await self.api.send_message(chat_id, f"🌐 *Network Info:*\n```\n{info}\n```")
            self.analytics.log_pc_control()
        except Exception as e:
            await self.api.send_message(chat_id, f"❌ Network info error: {e}")

    async def _cmd_lock_pc(self, chat_id: int, user_id: int):
        """Lock workstation where supported."""
        try:
            if _is_windows():
                subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], timeout=5)
            elif sys.platform == "darwin":
                subprocess.run(["/System/Library/CoreServices/Menu Extras/User.menu/Contents/Resources/CGSession", "-suspend"], timeout=5)
            else:
                return await self._send_platform_unsupported(chat_id, "Lock PC")
            await self.api.send_message(chat_id, "🔒 PC locked!")
            self.analytics.log_pc_control()
        except Exception as e:
            await self.api.send_message(chat_id, f"❌ Lock failed: {e}")

    async def _cmd_brightness(self, chat_id: int, user_id: int, level: str):
        """Set brightness where safely supported."""
        if not _is_windows():
            await self._send_platform_unsupported(chat_id, "Brightness control")
            return
        try:
            if str(level).lower() == "up":
                brightness_val = 100
            elif str(level).lower() == "down":
                brightness_val = 30
            else:
                brightness_val = max(0, min(100, int(level)))
            subprocess.run(
                ["powershell", "-Command",
                 f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,{brightness_val})"],
                capture_output=True, timeout=10
            )
            await self.api.send_message(chat_id, f"🔆 Brightness: {brightness_val}%")
            self.analytics.log_pc_control()
        except Exception as e:
            await self.api.send_message(chat_id, f"❌ Brightness error: {e}")
    
    async def _cmd_type(self, chat_id: int, user_id: int, text: str):
        """Handle /type command."""
        if not text:
            await self.api.send_message(chat_id, "❌ Text chahiye!")
            return
        
        try:
            import pyautogui
            import pyperclip
            
            pyperclip.copy(text)
            if sys.platform == "darwin":
                pyautogui.hotkey('command', 'v')
            else:
                pyautogui.hotkey('ctrl', 'v')
            
            await self.api.send_message(
                chat_id,
                f"✅ Typed: {text[:50]}..."
            )
        except Exception as e:
            await self.api.send_message(chat_id, f"❌ Error: {e}")
    
    async def _cmd_stats(self, chat_id: int, user_id: int):
        """Handle /stats command."""
        stats = self.analytics.get_stats()
        top_users = self.analytics.get_top_users(5)
        top_commands = self.analytics.get_top_commands(5)
        
        stats_text = f"""
📊 *Usage Statistics*

*Messages:* {stats.total_messages}
*Commands:* {stats.total_commands}
*AI Responses:* {stats.ai_responses}
*PC Controls:* {stats.pc_controls}

*Top Users:*
"""
        for name, count in top_users:
            stats_text += f"• {name}: {count}\n"
        
        stats_text += "\n*Top Commands:*\n"
        for cmd, count in top_commands:
            stats_text += f"• /{cmd}: {count}\n"
        
        await self.api.send_message(chat_id, stats_text)
    
    async def _cmd_users(self, chat_id: int, user_id: int):
        """Handle /users command (admin only)."""
        if self.security.get_user_role(chat_id, user_id) != UserRole.ADMIN:
            await self.api.send_message(chat_id, "⛔ Admin only command!")
            return
        
        all_users = self.users.get_all_users()
        
        users_text = f"👥 *Users ({len(all_users)}):*\n\n"
        
        for u in all_users[:20]:
            users_text += (
                f"• {u.first_name} (@{u.username})\n"
                f"  Role: {u.role.value}\n"
                f"  Messages: {u.message_count}\n\n"
            )
        
        await self.api.send_message(chat_id, users_text)
    
    async def _send_quick_actions(self, chat_id: int):
        """Sends inline keyboard with quick-action buttons."""
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "📸 Screenshot", "callback_data": "qa:screenshot"},
                    {"text": "📊 PC Status", "callback_data": "qa:pc_status"},
                ],
                [
                    {"text": "📱 Running Apps", "callback_data": "qa:apps"},
                    {"text": "🌐 Network Info", "callback_data": "qa:network"},
                ],
                [
                    {"text": "💾 Disk Info", "callback_data": "qa:disk"},
                    {"text": "🔒 Lock PC", "callback_data": "qa:lock"},
                ],
                [
                    {"text": "🔊 Vol Up", "callback_data": "qa:vol_up"},
                    {"text": "🔇 Mute", "callback_data": "qa:vol_mute"},
                    {"text": "🔉 Vol Down", "callback_data": "qa:vol_down"},
                ],
                [
                    {"text": "🔆 Brightness+", "callback_data": "qa:bright_up"},
                    {"text": "🔅 Brightness-", "callback_data": "qa:bright_down"},
                ],
            ]
        }
        await self.api.send_message(
            chat_id,
            "⚡ *Quick Actions* — Tap a button:",
            reply_markup=keyboard,
        )

    async def _handle_voice(self, chat_id: int, user_id: int, user_name: str, voice: dict):
        """Handle voice message — download, transcribe with Gemini, process as text."""
        try:
            file_id = voice.get("file_id", "")
            if not file_id:
                return

            await self.api.send_chat_action(chat_id, "typing")

            # Download voice file
            tmp_dir = os.path.join(os.path.expanduser("~"), ".shell_telegram_tmp")
            os.makedirs(tmp_dir, exist_ok=True)
            voice_path = os.path.join(tmp_dir, f"voice_{user_id}_{int(time.time())}.ogg")

            downloaded = await self.api.download_file(file_id, voice_path)
            if not downloaded:
                await self.api.send_message(chat_id, "❌ Voice download failed")
                return

            # Transcribe using Gemini
            api_key = config.get_str("GOOGLE_API_KEY") or config.get_str("GEMINI_API_KEY")
            if not api_key:
                await self.api.send_message(chat_id, "❌ Gemini API key not configured")
                return

            try:
                from google import genai
                from google.genai import types

                client = genai.Client(api_key=api_key)

                # Upload audio file
                with open(voice_path, "rb") as f:
                    audio_data = f.read()

                response = await asyncio.to_thread(
                    client.models.generate_content,
                    model="gemini-2.5-flash",
                    contents=[
                        types.Content(parts=[
                            types.Part.from_bytes(data=audio_data, mime_type="audio/ogg"),
                            types.Part.from_text("Transcribe this audio message. Return ONLY the transcription text, nothing else. If Hindi/Hinglish, write in Roman script."),
                        ])
                    ],
                )

                transcribed = ""
                if response and response.candidates:
                    candidate = response.candidates[0]
                    if candidate.content and candidate.content.parts:
                        for part in candidate.content.parts:
                            if hasattr(part, 'text') and part.text:
                                transcribed = part.text.strip()
                                break

                if transcribed:
                    await self.api.send_message(chat_id, f"🎤 _\"{transcribed}\"_")
                    # Process as text command
                    reply = await self._smart_execute(chat_id, user_id, user_name, transcribed)
                    self.memory.add_message(chat_id, user_name, f"[Voice] {transcribed}")
                    self.memory.add_message(chat_id, "Shell", reply)
                else:
                    await self.api.send_message(chat_id, "❌ Voice samajh nahi aayi, dobara try karo")

            except Exception as e:
                self.logger.error(f"Voice transcription error: {e}")
                await self.api.send_message(chat_id, f"❌ Voice processing error: {e}")

            # Cleanup
            try:
                os.remove(voice_path)
            except OSError as _e:
                logger.debug("ignored OSError: %s", _e)
        except Exception as e:
            self.logger.error(f"Voice handling error: {e}")
            await self.api.send_message(chat_id, f"❌ Voice error: {e}")

    async def _handle_photo(self, chat_id: int, user_id: int, user_name: str,
                            photo_list: list, caption: str = ""):
        """Handle photo message — download, describe with Gemini Vision."""
        try:
            # Get largest photo (last in array)
            photo = photo_list[-1] if photo_list else None
            if not photo:
                return

            file_id = photo.get("file_id", "")
            if not file_id:
                return

            await self.api.send_chat_action(chat_id, "typing")

            # Download photo
            tmp_dir = os.path.join(os.path.expanduser("~"), ".shell_telegram_tmp")
            os.makedirs(tmp_dir, exist_ok=True)
            photo_path = os.path.join(tmp_dir, f"photo_{user_id}_{int(time.time())}.jpg")

            downloaded = await self.api.download_file(file_id, photo_path)
            if not downloaded:
                await self.api.send_message(chat_id, "❌ Photo download failed")
                return

            # Analyze with Gemini Vision
            api_key = config.get_str("GOOGLE_API_KEY") or config.get_str("GEMINI_API_KEY")
            if not api_key:
                await self.api.send_message(chat_id, "❌ Gemini API key not configured")
                return

            try:
                from google import genai
                from google.genai import types

                client = genai.Client(api_key=api_key)

                with open(photo_path, "rb") as f:
                    image_data = f.read()

                prompt = caption if caption else "Describe this image in detail. Reply in Hinglish (Hindi+English mix). Be concise, 2-3 sentences."

                response = await asyncio.to_thread(
                    client.models.generate_content,
                    model="gemini-2.5-flash",
                    contents=[
                        types.Content(parts=[
                            types.Part.from_bytes(data=image_data, mime_type="image/jpeg"),
                            types.Part.from_text(prompt),
                        ])
                    ],
                )

                description = ""
                if response and response.candidates:
                    candidate = response.candidates[0]
                    if candidate.content and candidate.content.parts:
                        for part in candidate.content.parts:
                            if hasattr(part, 'text') and part.text:
                                description = part.text.strip()
                                break

                if description:
                    await self.api.send_message(chat_id, f"👁️ {description}")
                else:
                    await self.api.send_message(chat_id, "❌ Image analyze nahi ho payi")

            except Exception as e:
                self.logger.error(f"Photo analysis error: {e}")
                await self.api.send_message(chat_id, f"❌ Photo error: {e}")

            # Cleanup
            try:
                os.remove(photo_path)
            except OSError as _e:
                logger.debug("ignored OSError: %s", _e)
        except Exception as e:
            self.logger.error(f"Photo handling error: {e}")

    async def _handle_callback(self, callback: dict):
        """Handles callback query (button press) — executes quick actions."""
        try:
            chat_id = callback.get("message", {}).get("chat", {}).get("id", 0)
            user_id = callback.get("from", {}).get("id", 0)
            data = callback.get("data", "")
            callback_id = callback.get("id", "")

            if not data or not chat_id:
                return

            # Quick action buttons
            if data.startswith("qa:"):
                action = data[3:]
                await self.api.answer_callback_query(callback_id, f"Executing...")

                action_map = {
                    "screenshot": ("take_screenshot", {}),
                    "pc_status": ("pc_status", {}),
                    "apps": ("list_apps", {}),
                    "network": ("network_info", {}),
                    "disk": ("disk_info", {}),
                    "lock": ("lock_pc", {}),
                    "vol_up": ("control_volume", {"action": "up"}),
                    "vol_down": ("control_volume", {"action": "down"}),
                    "vol_mute": ("control_volume", {"action": "mute"}),
                    "bright_up": ("set_brightness", {"level": "up"}),
                    "bright_down": ("set_brightness", {"level": "down"}),
                }

                if action in action_map:
                    tool_name, tool_args = action_map[action]
                    await self._execute_tool(chat_id, user_id, tool_name, tool_args)
                else:
                    await self.api.send_message(chat_id, f"⚠️ Unknown action: {action}")

            elif data.startswith("action:"):
                action = data.replace("action:", "")
                await self.api.answer_callback_query(
                    callback_id,
                    f"Executing: {action}",
                    show_alert=True
                )

        except Exception as e:
            self.logger.error(f"Callback handling error: {e}")


# =============================================================================
# 🌍 GLOBAL INSTANCE
# =============================================================================

bot = ShellTelegramBot()
logger = get_logger("shell_telegram")


# =============================================================================
# 🚀 TOOL WRAPPERS
# =============================================================================

if not FUNCTION_TOOL_AVAILABLE:
    def function_tool(func):
        return func


@function_tool
async def set_telegram_token_tool(token: str) -> str:
    """
    🔑 Set Telegram Bot Token from @BotFather.
    
    Args:
        token: Bot token (e.g., "123456:ABC-DEF1234...")
    
    Examples:
        - "Set telegram token to 123456:ABC..."
        - "Configure telegram token"
    """
    token = str(token or "").strip()
    if not _telegram_token_shape_ok(token):
        return "❌ Invalid Telegram token format. @BotFather se full bot token paste karo."
    
    # Persist to .env through the same safe API-key manager used by the UI.
    try:
        from shell_api_manager import set_api_key

        ok, msg = set_api_key("TELEGRAM_BOT_TOKEN", token)
        if not ok:
            return f"❌ Token save failed: {msg}"
    except Exception as exc:
        return f"❌ Token save failed: {exc}"

    os.environ["TELEGRAM_BOT_TOKEN"] = token
    _reload_runtime_config()
    
    # Test token
    api = TelegramAPI(token)
    result = await api.get_me()
    
    if result.get("ok"):
        bot_info = result.get("result", {})
        return (
            f"✅ *Token saved!*\n\n"
            f"🤖 Bot: {bot_info.get('first_name', 'Shell Bot')}\n"
            f"📱 Username: @{bot_info.get('username', '?')}\n\n"
            f"Ab 'start telegram bot' bolo!"
        )
    
    return f"❌ Invalid token: {result.get('error')}"


@function_tool
async def start_telegram_bot() -> str:
    """
    🚀 Start Telegram Bot.
    
    Examples:
        - "Start telegram bot"
        - "Activate telegram"
    """
    return await bot.start()


@function_tool
async def stop_telegram_bot() -> str:
    """
    🛑 Stop Telegram Bot.
    
    Examples:
        - "Stop telegram bot"
        - "Deactivate telegram"
    """
    return await bot.stop()


@function_tool
async def telegram_bot_status() -> str:
    """
    📊 Check Telegram Bot status.
    
    Examples:
        - "Telegram bot status"
        - "Is telegram active?"
    """
    _reload_runtime_config()
    allowed_count = len(set(Config.ALLOWED_USERS) | set(Config.ADMIN_CHAT_IDS))
    remote_state = "ON" if Config.REMOTE_CONTROL_ENABLED else "OFF"
    terminal_state = "ON" if Config.ALLOW_TERMINAL else "OFF"
    token_state = "configured" if Config.TELEGRAM_BOT_TOKEN else "missing"
    token_shape = "valid-shape" if _telegram_token_shape_ok(Config.TELEGRAM_BOT_TOKEN) else "invalid/missing"
    task_state = "running" if bot._task_running() else ("stopped" if not bot.task else "ended")
    bot_name = bot.bot_info.get("username") or Config.BOT_USERNAME
    common = (
        f"🔑 Token: {token_state} ({token_shape})\n"
        f"🤖 Bot: @{bot_name}\n"
        f"🖥️ Platform: {_platform_label()}\n"
        f"🖥️ PC control: {remote_state}\n"
        f"👤 Allowed chats: {allowed_count}\n"
        f"⌨️ Terminal access: {terminal_state}\n"
        f"🧵 Polling task: {task_state}\n"
        f"📡 Last poll: {_iso_or_never(bot.last_poll_at)}\n"
        f"📥 Last update: {_iso_or_never(bot.last_update_at)}\n"
        f"⚠️ Last error: {bot.last_error or (bot.api.last_error if bot.api else '') or 'none'}"
    )
    if bot.active:
        stats = bot.analytics.get_stats()
        return (
            f"✅ *Telegram Bot: ACTIVE*\n\n"
            f"{common}\n\n"
            f"📊 Messages: {stats.total_messages}\n"
            f"🔧 Commands: {stats.total_commands}\n"
            f"🤖 AI: {stats.ai_responses}\n"
            f"💻 PC: {stats.pc_controls}"
        )
    
    return (
        "❌ Telegram Bot: INACTIVE\n\n"
        f"{common}"
    )


@function_tool
async def set_telegram_remote_config_tool(
    allowed_chat_ids: str = "",
    remote_control_enabled: bool = False,
    allow_terminal: bool = False,
) -> str:
    """
    Save Telegram remote-control safety settings.

    Args:
        allowed_chat_ids: Comma-separated chat IDs allowed to control this PC.
        remote_control_enabled: Enable non-destructive PC-control commands.
        allow_terminal: Enable Telegram terminal commands. Dangerous; default false.
    """
    ids = ",".join(str(i) for i in _parse_chat_ids(allowed_chat_ids))
    try:
        from shell_settings_manager import set_settings

        ok, msg, _applied = set_settings({
            "telegram_allowed_chat_ids": ids,
            "telegram_remote_control_enabled": bool(remote_control_enabled),
            "telegram_allow_terminal": bool(allow_terminal),
        })
        if not ok:
            return f"❌ Telegram remote config save failed: {msg}"
    except Exception as exc:
        return f"❌ Telegram remote config save failed: {exc}"

    _reload_runtime_config()
    return (
        "✅ Telegram remote-control settings saved.\n"
        f"Allowed chat IDs: {ids or 'none'}\n"
        f"PC control: {'ON' if Config.REMOTE_CONTROL_ENABLED else 'OFF'}\n"
        f"Terminal access: {'ON' if Config.ALLOW_TERMINAL else 'OFF'}"
    )


@function_tool
async def send_telegram_message_tool(message: str) -> str:
    """
    📤 Send message via Telegram.
    
    Args:
        message: Message text
    
    Examples:
        - "Send telegram message: Hello!"
        - "Notify via telegram"
    """
    _reload_runtime_config()
    target_chat = bot.authorized_chat_id
    if not target_chat and Config.ALLOWED_USERS:
        target_chat = Config.ALLOWED_USERS[0]
    if not target_chat:
        return "❌ No Telegram chat ID available. Send /start to the bot or add allowed chat ID in Settings."
    if bot.api is None:
        bot.api = TelegramAPI(Config.TELEGRAM_BOT_TOKEN)
    if not Config.TELEGRAM_BOT_TOKEN:
        return "❌ Telegram token missing."
    
    success = await bot.api.send_message(
        target_chat,
        message
    )
    
    if success:
        return f"✅ Message sent via Telegram!"
    
    return "❌ Failed to send message."


@function_tool
async def telegram_chat_log() -> str:
    """
    📜 View Telegram chat log.
    
    Examples:
        - "Show telegram chat log"
        - "Telegram history"
    """
    stats = bot.analytics.get_stats()
    top_users = bot.analytics.get_top_users(10)
    
    log_text = "📜 *Telegram Chat Log*\n\n"
    log_text += f"Total Messages: {stats.total_messages}\n\n"
    log_text += "*Top Users:*\n"
    
    for name, count in top_users:
        log_text += f"• {name}: {count}\n"
    
    return log_text


@function_tool
async def get_telegram_stats_tool() -> str:
    """
    📊 Get detailed Telegram statistics.
    
    Examples:
        - "Telegram statistics"
        - "Show telegram usage"
    """
    stats = bot.analytics.get_stats()
    
    uptime_hours = stats.uptime_seconds / 3600
    
    return f"""
📊 *Telegram Statistics*

⏱️ Uptime: {uptime_hours:.1f} hours
👥 Users: {stats.total_users}
📨 Messages: {stats.total_messages}
🔧 Commands: {stats.total_commands}
🤖 AI Responses: {stats.ai_responses}
💻 PC Controls: {stats.pc_controls}
"""


# =============================================================================
# 🧪 TEST MODE
# =============================================================================

if __name__ == "__main__":
    if sys.platform == 'win32':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass  # Non-critical: encoding reconfigure not supported
    
    logger.info("[SHELL_TELEGRAM_MEGA] Test Mode")
    logger.info("=" * 60)

    async def test_telegram():
        # Test 1: Status
        logger.info("[TEST 1] Bot status...")
        result = await telegram_bot_status()
        logger.info(result)

        # Test 2: Stats
        logger.info("[TEST 2] Statistics...")
        result = await get_telegram_stats_tool()
        logger.info(result)

        # Test 3: Chat log
        logger.info("[TEST 3] Chat log...")
        result = await telegram_chat_log()
        logger.info(result)

        logger.info("[TEST] Tests completed!")
    
    asyncio.run(test_telegram())
