# =============================================================================
# Shell keyboard and mouse control
# =============================================================================
# Advanced Human-Machine Interface with:
# - ✅ Proper Error Handling & Logging
# - ✅ Security Validation & Rate Limiting
# - ✅ Performance Optimization & Caching
# - ✅ Type Safety & Documentation
# - ✅ Gesture Recognition & Smart Automation
# - ✅ Multi-Monitor Support
# - ✅ Accessibility Features
# =============================================================================

import asyncio
import time
import logging
import re
import json
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Union
from pathlib import Path
from functools import wraps
from contextlib import contextmanager
import random
import threading
from collections import deque

# Lazy imports for performance
pyautogui = None
pynput_keyboard = None
pynput_mouse = None
pyperclip_module = None

# =============================================================================
# 📊 CONFIGURATION & CONSTANTS
# =============================================================================

class Config:
    """Centralized configuration for keyboard/mouse control."""
    
    # Timing Configuration (in seconds)
    MOUSE_MOVE_DURATION = 0.25
    MOUSE_CLICK_DURATION = 0.35
    SCROLL_DURATION = 0.15
    TYPE_DELAY_MIN = 0.015
    TYPE_DELAY_MAX = 0.055
    HOTKEY_HOLD_DURATION = 0.05
    GESTURE_DURATION = 0.5
    
    # Security & Rate Limiting
    MAX_CLICKS_PER_MINUTE = 60
    MAX_SCROLLS_PER_MINUTE = 120
    MAX_KEYSTROKES_PER_MINUTE = 600
    MAX_TEXT_LENGTH = 10000
    RATE_LIMIT_WINDOW = 60  # seconds
    
    # Performance
    CLIPBOARD_PASTE_THRESHOLD = 50  # chars
    ENABLE_HUMANIZATION = True
    ENABLE_LOGGING = True
    
    # Multi-Monitor
    PRIMARY_MONITOR_ONLY = False
    
    # Accessibility
    LARGE_MOVEMENT_THRESHOLD = 500  # pixels
    SLOW_MODE_MULTIPLIER = 2.0

# =============================================================================
# 🛡️ SECURITY & VALIDATION
# =============================================================================

class SecurityValidator:
    """Validates inputs to prevent malicious usage."""
    
    DANGEROUS_KEY_COMBINATIONS = {
        ('ctrl', 'alt', 'delete'): "Task Manager access restricted",
        ('win', 'r'): "Run dialog access restricted",
        ('ctrl', 'shift', 'esc'): "Task Manager access restricted",
        ('alt', 'f4'): "Close window restricted in bulk",
    }
    
    BLOCKED_TEXT_PATTERNS = [
        r'password\s*[:=]\s*\S+',  # Password patterns
        r'api[_-]?key\s*[:=]\s*\S+',  # API keys
        r'secret\s*[:=]\s*\S+',  # Secrets
    ]
    
    @classmethod
    def validate_hotkey(cls, keys: List[str]) -> Tuple[bool, str]:
        """Validates hotkey combinations for security."""
        key_set = tuple(sorted([k.lower() for k in keys]))
        
        for blocked_combo, reason in cls.DANGEROUS_KEY_COMBINATIONS.items():
            if all(k in key_set for k in blocked_combo):
                return False, f"⚠️ Security: {reason}"
        
        return True, "OK"
    
    @classmethod
    def validate_text(cls, text: str) -> Tuple[bool, str]:
        """Validates text for sensitive patterns."""
        if len(text) > Config.MAX_TEXT_LENGTH:
            return False, f"❌ Text too long ({len(text)} > {Config.MAX_TEXT_LENGTH})"
        
        for pattern in cls.BLOCKED_TEXT_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return False, "⚠️ Security: Sensitive pattern detected"
        
        return True, "OK"
    
    @classmethod
    def validate_coordinates(cls, x: int, y: int) -> Tuple[bool, str]:
        """Validates screen coordinates."""
        try:
            import pyautogui
            screen_width, screen_height = pyautogui.size()
            
            if not (0 <= x <= screen_width * 2):  # Allow multi-monitor
                return False, f"❌ X coordinate {x} out of bounds (0-{screen_width * 2})"
            if not (0 <= y <= screen_height * 2):
                return False, f"❌ Y coordinate {y} out of bounds (0-{screen_height * 2})"
            
            return True, "OK"
        except Exception as e:
            return False, f"❌ Validation error: {e}"

# =============================================================================
# 📈 RATE LIMITER
# =============================================================================

class RateLimiter:
    """Prevents abuse through rate limiting."""
    
    def __init__(self, max_actions: int, window_seconds: int):
        self.max_actions = max_actions
        self.window_seconds = window_seconds
        self.timestamps = deque()
        self._lock = threading.Lock()
    
    def can_proceed(self) -> Tuple[bool, int]:
        """Returns (can_proceed, wait_time_seconds)."""
        with self._lock:
            now = time.time()
            
            # Remove old timestamps
            while self.timestamps and self.timestamps[0] < now - self.window_seconds:
                self.timestamps.popleft()
            
            if len(self.timestamps) >= self.max_actions:
                wait_time = self.timestamps[0] + self.window_seconds - now
                return False, max(0, wait_time)
            
            self.timestamps.append(now)
            return True, 0
    
    def reset(self):
        """Resets the rate limiter."""
        with self._lock:
            self.timestamps.clear()

# =============================================================================
# 📝 ENHANCED LOGGING
# =============================================================================

class ActionLogger:
    """Centralized logging with file and console output."""
    
    def __init__(self, log_file: str = "control_log.txt", enable_console: bool = False):
        self.log_file = Path(log_file)
        self.enable_console = enable_console
        self._ensure_log_dir()
        
        # Setup proper logging
        self.logger = logging.getLogger("keyboard_mouse_ctrl")
        self.logger.setLevel(logging.INFO)
        
        # File handler
        if not self.logger.handlers:
            fh = logging.FileHandler(self.log_file, encoding='utf-8')
            fh.setLevel(logging.INFO)
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            fh.setFormatter(formatter)
            self.logger.addHandler(fh)
            
            if enable_console:
                ch = logging.StreamHandler()
                ch.setLevel(logging.INFO)
                ch.setFormatter(formatter)
                self.logger.addHandler(ch)
    
    def _ensure_log_dir(self):
        """Ensures log directory exists."""
        try:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"⚠️ Could not create log directory: {e}")
    
    def log_action(self, action: str, details: Dict = None):
        """Logs an action with optional details."""
        try:
            if details:
                message = f"{action} | {json.dumps(details, ensure_ascii=False)}"
            else:
                message = action
            
            self.logger.info(message)
        except Exception as e:
            print(f"⚠️ Logging failed: {e}")
    
    def log_error(self, action: str, error: Exception):
        """Logs an error with traceback."""
        try:
            self.logger.error(f"{action} | ERROR: {str(error)}", exc_info=True)
        except Exception as e:
            print(f"⚠️ Error logging failed: {e}")
    
    def log_warning(self, message: str):
        """Logs a warning."""
        try:
            self.logger.warning(message)
        except Exception as e:
            print(f"⚠️ Warning logging failed: {e}")

# =============================================================================
# 🎯 ADVANCED CONTROLLER
# =============================================================================

class AdvancedSafeController:
    """
    Keyboard & mouse controller with guarded automation features.
    
    Features:
    - ✅ Proper error handling with detailed messages
    - ✅ Rate limiting to prevent abuse
    - ✅ Security validation for inputs
    - ✅ Performance optimization with lazy loading
    - ✅ Multi-monitor support
    - ✅ Accessibility features
    - ✅ Gesture recognition
    - ✅ Smart clipboard integration
    """
    
    def __init__(self):
        self.active = False
        self.activation_time: Optional[float] = None
        self.session_id: str = f"session_{int(time.time())}"
        
        # Lazy-loaded components
        self._keyboard = None
        self._mouse = None
        self._pynput_keys = None
        self._pynput_button = None
        self._pyautogui = None
        self._pyperclip = None
        
        # Rate limiters
        self.click_limiter = RateLimiter(Config.MAX_CLICKS_PER_MINUTE, Config.RATE_LIMIT_WINDOW)
        self.scroll_limiter = RateLimiter(Config.MAX_SCROLLS_PER_MINUTE, Config.RATE_LIMIT_WINDOW)
        self.keystroke_limiter = RateLimiter(Config.MAX_KEYSTROKES_PER_MINUTE, Config.RATE_LIMIT_WINDOW)
        
        # Logger
        self.logger = ActionLogger()
        
        # Valid keys cache
        self.valid_keys = set("abcdefghijklmnopqrstuvwxyz1234567890")
        self.special_keys_map: Dict[str, str] = {}
        
        # Performance cache
        self._screen_size_cache: Optional[Tuple[int, int]] = None
        self._cache_timestamp: float = 0
        self._cache_ttl: float = 5.0  # seconds
        
        # State tracking
        self._last_position: Optional[Tuple[int, int]] = None
        self._movement_history: deque = deque(maxlen=100)
    
    # -------------------------------------------------------------------------
    # 🔧 LAZY LOADING & INITIALIZATION
    # -------------------------------------------------------------------------
    
    def _ensure_controllers(self) -> bool:
        """Lazy load all controllers with proper error handling."""
        if self._keyboard and self._mouse and self._pyautogui:
            return True
        
        try:
            # Import pyautogui
            import pyautogui
            self._pyautogui = pyautogui
            pyautogui.FAILSAFE = True  # Enable failsafe (mouse to corner)
            pyautogui.PAUSE = 0.05  # Small pause between actions
            
            # Import pynput
            from pynput.keyboard import Key, Controller as KeyboardController
            from pynput.mouse import Button, Controller as MouseController
            
            self._keyboard = KeyboardController()
            self._mouse = MouseController()
            self._pynput_keys = Key
            self._pynput_button = Button
            
            # Import pyperclip
            import pyperclip
            self._pyperclip = pyperclip
            
            # Setup special keys map
            self._setup_special_keys()
            
            self.logger.log_action("Controllers initialized successfully")
            return True
            
        except ImportError as e:
            self.logger.log_error("Controller import failed", e)
            print(f"❌ Required package not found: {e}")
            print("💡 Run: pip install pyautogui pynput pyperclip")
            return False
        except Exception as e:
            self.logger.log_error("Controller initialization failed", e)
            print(f"❌ Controller initialization error: {e}")
            return False
    
    def _setup_special_keys(self):
        """Setup special keys mapping."""
        if not self._pynput_keys:
            return
        
        self.special_keys_map = {
            # Navigation
            "enter": self._pynput_keys.enter,
            "return": self._pynput_keys.enter,
            "space": self._pynput_keys.space,
            "tab": self._pynput_keys.tab,
            "escape": self._pynput_keys.esc,
            "esc": self._pynput_keys.esc,
            
            # Modifiers
            "shift": self._pynput_keys.shift,
            "ctrl": self._pynput_keys.ctrl,
            "control": self._pynput_keys.ctrl,
            "alt": self._pynput_keys.alt,
            "win": self._pynput_keys.cmd,
            "cmd": self._pynput_keys.cmd,
            "command": self._pynput_keys.cmd,
            
            # Navigation keys
            "up": self._pynput_keys.up,
            "down": self._pynput_keys.down,
            "left": self._pynput_keys.left,
            "right": self._pynput_keys.right,
            "home": self._pynput_keys.home,
            "end": self._pynput_keys.end,
            "page_up": self._pynput_keys.page_up,
            "page_down": self._pynput_keys.page_down,
            "pgup": self._pynput_keys.page_up,
            "pgdn": self._pynput_keys.page_down,
            
            # Editing
            "backspace": self._pynput_keys.backspace,
            "delete": self._pynput_keys.delete,
            "del": self._pynput_keys.delete,
            "insert": self._pynput_keys.insert,
            
            # Function keys
            "f1": self._pynput_keys.f1,
            "f2": self._pynput_keys.f2,
            "f3": self._pynput_keys.f3,
            "f4": self._pynput_keys.f4,
            "f5": self._pynput_keys.f5,
            "f6": self._pynput_keys.f6,
            "f7": self._pynput_keys.f7,
            "f8": self._pynput_keys.f8,
            "f9": self._pynput_keys.f9,
            "f10": self._pynput_keys.f10,
            "f11": self._pynput_keys.f11,
            "f12": self._pynput_keys.f12,
            
            # Lock keys
            "caps_lock": self._pynput_keys.caps_lock,
            "capslock": self._pynput_keys.caps_lock,
            "num_lock": self._pynput_keys.num_lock,
            "scroll_lock": self._pynput_keys.scroll_lock,
            
            # Media keys (if supported)
            "volume_up": self._pynput_keys.media_volume_up,
            "volume_down": self._pynput_keys.media_volume_down,
            "volume_mute": self._pynput_keys.media_volume_mute,
            "play_pause": self._pynput_keys.media_play_pause,
        }
    
    # -------------------------------------------------------------------------
    # 🔒 SECURITY & STATE MANAGEMENT
    # -------------------------------------------------------------------------
    
    def activate(self, token: str = None, session_id: str = None) -> Tuple[bool, str]:
        """
        Activates the controller with security token.
        
        Args:
            token: Security token for activation
            session_id: Optional custom session ID
        
        Returns:
            Tuple of (success, message)
        """
        # Validate token
        env_token = os.getenv("SHELL_CTRL_TOKEN", "")
        if not env_token:
            # Auto-activate if no token is configured (local-only mode)
            pass
        elif token != env_token:
            # Hash the attempted token before logging — never log raw
            # token material, not even a 3-char preview (it narrows the
            # search space for a brute-forcing log reader).
            import hashlib as _hl
            token_hash = _hl.sha256((token or "").encode("utf-8")).hexdigest()[:12]
            self.logger.log_warning(f"Activation attempt failed (token_hash={token_hash}...).")
            return False, "🛑 Invalid activation token"
        
        if not self._ensure_controllers():
            return False, "❌ Controller initialization failed"
        
        self.active = True
        self.activation_time = time.time()
        self.session_id = session_id or f"session_{int(time.time())}"
        
        self.logger.log_action("Controller activated", {
            "session_id": self.session_id,
            "timestamp": datetime.now().isoformat()
        })
        
        return True, "✅ Controller activated successfully"
    
    def deactivate(self) -> str:
        """Deactivates the controller."""
        self.active = False
        duration = time.time() - self.activation_time if self.activation_time else 0
        
        self.logger.log_action("Controller deactivated", {
            "session_id": self.session_id,
            "duration_seconds": round(duration, 2)
        })
        
        return f"✅ Controller deactivated (session duration: {duration:.1f}s)"
    
    def is_active(self) -> bool:
        """Checks if controller is active."""
        return self.active
    
    def get_status(self) -> Dict:
        """Returns current controller status."""
        return {
            "active": self.active,
            "session_id": self.session_id,
            "activation_time": self.activation_time,
            "uptime_seconds": time.time() - self.activation_time if self.activation_time else 0,
            "screen_size": self._get_screen_size(),
            "last_position": self._last_position,
        }
    
    # -------------------------------------------------------------------------
    # 🖥️ SCREEN & POSITION UTILITIES
    # -------------------------------------------------------------------------
    
    def _get_screen_size(self, force_refresh: bool = False) -> Tuple[int, int]:
        """Gets screen size with caching."""
        now = time.time()
        
        if not force_refresh and self._screen_size_cache:
            if now - self._cache_timestamp < self._cache_ttl:
                return self._screen_size_cache
        
        try:
            if not self._ensure_controllers():
                return (1920, 1080)  # Default fallback
            
            size = self._pyautogui.size()
            self._screen_size_cache = (size.width, size.height)
            self._cache_timestamp = now
            return self._screen_size_cache
        except Exception as e:
            self.logger.log_error("Get screen size failed", e)
            return (1920, 1080)
    
    def _get_current_position(self) -> Tuple[int, int]:
        """Gets current mouse position."""
        try:
            if not self._ensure_controllers():
                return (0, 0)
            
            pos = self._pyautogui.position()
            self._last_position = (pos.x, pos.y)
            return (pos.x, pos.y)
        except Exception as e:
            self.logger.log_error("Get position failed", e)
            return (0, 0)
    
    def _record_movement(self, from_pos: Tuple[int, int], to_pos: Tuple[int, int], action: str):
        """Records movement for analytics and debugging."""
        self._movement_history.append({
            "timestamp": time.time(),
            "action": action,
            "from": from_pos,
            "to": to_pos,
            "distance": ((to_pos[0] - from_pos[0])**2 + (to_pos[1] - from_pos[1])**2)**0.5
        })
    
    # -------------------------------------------------------------------------
    # 🖱️ MOUSE MOVEMENT - ADVANCED
    # -------------------------------------------------------------------------
    
    async def move_cursor(self, direction: str, distance: int = 100, 
                         speed: str = "normal") -> str:
        """
        Moves cursor in a direction with humanized movement.
        
        Args:
            direction: "up", "down", "left", "right", "up-left", "up-right", etc.
            distance: Pixels to move
            speed: "slow", "normal", "fast"
        
        Returns:
            Status message
        """
        if not self.is_active():
            return "🛑 Controller is inactive. Activate first."
        
        # Validate direction
        valid_directions = ["up", "down", "left", "right", 
                          "up-left", "up-right", "down-left", "down-right",
                          "top-left", "top-right", "bottom-left", "bottom-right"]
        
        if direction.lower() not in valid_directions:
            return f"❌ Invalid direction: {direction}. Valid: {', '.join(valid_directions)}"
        
        # Validate distance
        if not isinstance(distance, int) or distance < 0:
            return "❌ Distance must be a positive integer"
        
        try:
            from_pos = self._get_current_position()
            
            # Calculate offsets for all 8 directions
            x_offset, y_offset = 0, 0
            if direction == "left":
                x_offset = -distance
            elif direction == "right":
                x_offset = distance
            elif direction == "up":
                y_offset = -distance
            elif direction == "down":
                y_offset = distance
            elif direction == "up-left":
                x_offset = -distance
                y_offset = -distance
            elif direction == "up-right":
                x_offset = distance
                y_offset = -distance
            elif direction == "down-left":
                x_offset = -distance
                y_offset = distance
            elif direction == "down-right":
                x_offset = distance
                y_offset = distance
            elif direction in ["top-left", "top-right", "bottom-left", "bottom-right"]:
                # Move to corners
                screen_w, screen_h = self._get_screen_size()
                if "top" in direction:
                    y_offset = -from_pos[1] + 50
                else:
                    y_offset = screen_h - from_pos[1] - 50
                if "left" in direction:
                    x_offset = -from_pos[0] + 50
                else:
                    x_offset = screen_w - from_pos[0] - 50
            
            # Calculate duration based on speed
            speed_multiplier = {"slow": Config.SLOW_MODE_MULTIPLIER, "normal": 1.0, "fast": 0.5}
            duration = Config.MOUSE_MOVE_DURATION * speed_multiplier.get(speed, 1.0)
            
            # Execute movement with humanization
            if Config.ENABLE_HUMANIZATION:
                self._pyautogui.move(x_offset, y_offset, duration=duration, 
                                    tween=self._pyautogui.easeInOutQuad)
            else:
                self._pyautogui.move(x_offset, y_offset)
            
            to_pos = self._get_current_position()
            self._record_movement(from_pos, to_pos, f"move_{direction}")
            
            self.logger.log_action("Mouse moved", {
                "direction": direction,
                "distance": distance,
                "from": from_pos,
                "to": to_pos
            })
            
            return f"🖱️ Mouse glided {direction} by {distance}px ({from_pos} → {to_pos})"
            
        except Exception as e:
            self.logger.log_error("Move cursor failed", e)
            return f"❌ Move cursor error: {str(e)}"
    
    async def move_cursor_to_position(self, x: int, y: int, 
                                     speed: str = "normal",
                                     smooth: bool = True) -> str:
        """
        Moves cursor to absolute coordinates with precision.
        
        Args:
            x: Target X coordinate
            y: Target Y coordinate
            speed: "slow", "normal", "fast"
            smooth: Enable smooth animation
        
        Returns:
            Status message
        """
        if not self.is_active():
            return "🛑 Controller is inactive. Activate first."
        
        # Validate coordinates
        valid, msg = SecurityValidator.validate_coordinates(x, y)
        if not valid:
            return msg
        
        try:
            from_pos = self._get_current_position()
            
            # Calculate duration
            speed_multiplier = {"slow": Config.SLOW_MODE_MULTIPLIER, "normal": 1.0, "fast": 0.5}
            duration = Config.MOUSE_CLICK_DURATION * speed_multiplier.get(speed, 1.0)
            
            # Execute movement
            if smooth and Config.ENABLE_HUMANIZATION:
                self._pyautogui.moveTo(x, y, duration=duration, 
                                      tween=self._pyautogui.easeInOutQuad)
            else:
                self._pyautogui.moveTo(x, y)
            
            to_pos = self._get_current_position()
            self._record_movement(from_pos, to_pos, "move_to_position")
            
            self.logger.log_action("Mouse moved to position", {
                "target": (x, y),
                "actual": to_pos,
                "from": from_pos
            })
            
            return f"🎯 Precision targeting: ({from_pos[0]}, {from_pos[1]}) → ({to_pos[0]}, {to_pos[1]})"
            
        except Exception as e:
            self.logger.log_error("Move to position failed", e)
            return f"❌ Position targeting error: {str(e)}"
    
    async def move_cursor_to_element(self, element_description: str) -> str:
        """
        🆕 NEW: Moves cursor to a UI element based on description.
        Uses vision engine to find element.
        
        Args:
            element_description: Description of element (e.g., "Submit button", "Search box")
        
        Returns:
            Status message
        """
        if not self.is_active():
            return "🛑 Controller is inactive"
        
        try:
            # Import vision engine
            from vision_engine import vision_engine
            
            # Find element on screen
            result = await vision_engine.find_element_on_screen(element_description)
            
            if result.get("found"):
                x, y = result["coordinates"]
                return await self.move_cursor_to_position(x, y)
            else:
                return f"❌ Element not found: {element_description}"
                
        except ImportError:
            return "❌ Vision engine not available"
        except Exception as e:
            self.logger.log_error("Find element failed", e)
            return f"❌ Element search error: {str(e)}"
    
    # -------------------------------------------------------------------------
    # 🖱️ MOUSE CLICKS - ADVANCED
    # -------------------------------------------------------------------------
    
    async def mouse_click(self, button: str = "left", 
                         count: int = 1,
                         hold_duration: float = 0.05) -> str:
        """
        Performs mouse click(s) with validation.
        
        Args:
            button: "left", "right", "middle", "double"
            count: Number of clicks (1-5)
            hold_duration: How long to hold button
        
        Returns:
            Status message
        """
        if not self.is_active():
            return "🛑 Controller is inactive"
        
        # Validate button
        valid_buttons = ["left", "right", "middle", "double", "triple"]
        if button.lower() not in valid_buttons:
            return f"❌ Invalid button: {button}. Valid: {', '.join(valid_buttons)}"
        
        # Validate count
        if not isinstance(count, int) or count < 1 or count > 5:
            return "❌ Count must be between 1 and 5"
        
        # Rate limit check
        can_proceed, wait_time = self.click_limiter.can_proceed()
        if not can_proceed:
            return f"⏱️ Rate limit exceeded. Wait {wait_time:.1f}s"
        
        try:
            # Map button
            button_map = {
                "left": self._pynput_button.left,
                "right": self._pynput_button.right,
                "middle": self._pynput_button.middle,
            }
            
            click_count = 2 if button == "double" else (3 if button == "triple" else count)
            pynput_button = button_map.get(button.lower(), self._pynput_button.left)
            
            # Execute clicks
            for i in range(click_count):
                self._mouse.click(pynput_button, 1)
                if i < click_count - 1:
                    await asyncio.sleep(0.1)
            
            self.logger.log_action("Mouse clicked", {
                "button": button,
                "count": click_count,
                "position": self._get_current_position()
            })
            
            return f"🖱️ {button.capitalize()} click{'s' if click_count > 1 else ''} executed"
            
        except Exception as e:
            self.logger.log_error("Mouse click failed", e)
            return f"❌ Click error: {str(e)}"
    
    async def mouse_drag(self, from_x: int, from_y: int, 
                        to_x: int, to_y: int,
                        duration: float = 0.5) -> str:
        """
        🆕 NEW: Performs drag operation.
        
        Args:
            from_x, from_y: Start position
            to_x, to_y: End position
            duration: Drag duration in seconds
        
        Returns:
            Status message
        """
        if not self.is_active():
            return "🛑 Controller is inactive"
        
        try:
            # Move to start position
            await self.move_cursor_to_position(from_x, from_y, speed="fast")
            await asyncio.sleep(0.1)
            
            # Press and hold
            self._mouse.press(self._pynput_button.left)
            
            # Move to end position
            if Config.ENABLE_HUMANIZATION:
                self._pyautogui.dragTo(to_x, to_y, duration=duration,
                                      tween=self._pyautogui.easeInOutQuad)
            else:
                self._pyautogui.dragTo(to_x, to_y)
            
            # Release
            self._mouse.release(self._pynput_button.left)
            
            self.logger.log_action("Mouse drag", {
                "from": (from_x, from_y),
                "to": (to_x, to_y)
            })
            
            return f"🖱️ Drag completed: ({from_x}, {from_y}) → ({to_x}, {to_y})"
            
        except Exception as e:
            self.logger.log_error("Mouse drag failed", e)
            return f"❌ Drag error: {str(e)}"
    
    # -------------------------------------------------------------------------
    # 📜 SCROLLING - ADVANCED
    # -------------------------------------------------------------------------
    
    async def scroll_cursor(self, direction: str, amount: int = 10,
                           smooth: bool = True) -> str:
        """
        Scrolls with smooth animation and rate limiting.
        
        Args:
            direction: "up", "down", "left", "right"
            amount: Scroll amount (positive integer)
            smooth: Enable smooth scrolling
        
        Returns:
            Status message
        """
        if not self.is_active():
            return "🛑 Controller is inactive"
        
        # Validate direction
        valid_directions = ["up", "down", "left", "right"]
        if direction.lower() not in valid_directions:
            return f"❌ Invalid direction: {direction}. Valid: {', '.join(valid_directions)}"
        
        # Validate amount
        if not isinstance(amount, int) or amount < 1:
            return "❌ Amount must be a positive integer"
        
        # Rate limit check
        can_proceed, wait_time = self.scroll_limiter.can_proceed()
        if not can_proceed:
            return f"⏱️ Rate limit exceeded. Wait {wait_time:.1f}s"
        
        try:
            if direction in ["up", "down"]:
                scroll_amount = amount if direction == "up" else -amount
                if smooth:
                    # Smooth scroll in steps
                    step_size = max(1, amount // 5)
                    for _ in range(5):
                        self._mouse.scroll(0, step_size if direction == "up" else -step_size)
                        await asyncio.sleep(Config.SCROLL_DURATION / 5)
                else:
                    self._mouse.scroll(0, scroll_amount)
            else:
                # Horizontal scroll (if supported)
                scroll_amount = amount if direction == "right" else -amount
                self._mouse.scroll(scroll_amount, 0)
            
            self.logger.log_action("Mouse scrolled", {
                "direction": direction,
                "amount": amount
            })
            
            return f"📜 Scrolled {direction} (amount: {amount})"
            
        except Exception as e:
            # Fallback to pyautogui
            try:
                if direction == "up":
                    self._pyautogui.scroll(amount * 100)
                elif direction == "down":
                    self._pyautogui.scroll(-amount * 100)
                elif direction == "left":
                    self._pyautogui.hscroll(-amount * 100)
                elif direction == "right":
                    self._pyautogui.hscroll(amount * 100)
                
                return f"📜 Scrolled {direction} (fallback method)"
            except Exception as fallback_error:
                self.logger.log_error("Scroll failed", e)
                return f"❌ Scroll error: {str(e)}"
    
    # -------------------------------------------------------------------------
    # ⌨️ TYPING - ADVANCED
    # -------------------------------------------------------------------------
    
    async def type_text(self, text: str, 
                       use_clipboard: bool = True,
                       simulate_human: bool = True) -> str:
        """
        Types text with smart clipboard fallback and humanization.
        
        Args:
            text: Text to type
            use_clipboard: Use clipboard for long text
            simulate_human: Simulate human typing patterns
        
        Returns:
            Status message
        """
        if not self.is_active():
            return "🛑 Controller is inactive"
        
        # Validate text
        valid, msg = SecurityValidator.validate_text(text)
        if not valid:
            return msg
        
        if not text:
            return "❌ Text is empty"
        
        # Rate limit check
        can_proceed, wait_time = self.keystroke_limiter.can_proceed()
        if not can_proceed and len(text) > 10:
            return f"⏱️ Rate limit exceeded. Wait {wait_time:.1f}s"
        
        try:
            # Normalize line endings
            text = text.replace("\r\n", "\n")
            
            # Smart decision: Use clipboard for long/complex text
            use_clip = (use_clipboard and 
                       (len(text) > Config.CLIPBOARD_PASTE_THRESHOLD or 
                        "\n" in text or 
                        "{" in text or 
                        "</" in text))
            
            if use_clip:
                return await self._type_with_clipboard(text)
            else:
                return await self._type_character_by_character(text, simulate_human)
                
        except Exception as e:
            self.logger.log_error("Type text failed", e)
            return f"❌ Type error: {str(e)}"
    
    async def _type_with_clipboard(self, text: str) -> str:
        """Types text using clipboard paste (fast method)."""
        try:
            # Copy to clipboard
            self._pyperclip.copy(text)
            await asyncio.sleep(0.1)
            
            # Paste with Ctrl+V
            with self._pyautogui.hold('ctrl'):
                self._pyautogui.press('v')
            
            self.logger.log_action("Text pasted via clipboard", {
                "length": len(text),
                "preview": text[:50] + "..." if len(text) > 50 else text
            })
            
            return f"📋 Pasted {len(text)} characters via clipboard"
            
        except Exception as e:
            self.logger.log_warning("Clipboard paste failed, falling back to typing")
            return await self._type_character_by_character(text)
    
    async def _type_character_by_character(self, text: str, 
                                          simulate_human: bool) -> str:
        """Types text character by character with humanization."""
        typed_count = 0
        
        for char in text:
            if char == "\n":
                self._keyboard.press(self._pynput_keys.enter)
                self._keyboard.release(self._pynput_keys.enter)
                await asyncio.sleep(0.05)
            elif char == "\t":
                self._keyboard.press(self._pynput_keys.tab)
                self._keyboard.release(self._pynput_keys.tab)
                await asyncio.sleep(0.02)
            elif not char.isprintable():
                continue
            else:
                try:
                    self._keyboard.press(char)
                    self._keyboard.release(char)
                    typed_count += 1
                    
                    # Human-like timing variation
                    if simulate_human and Config.ENABLE_HUMANIZATION:
                        delay = random.uniform(Config.TYPE_DELAY_MIN, Config.TYPE_DELAY_MAX)
                        await asyncio.sleep(delay)
                except Exception:
                    continue
        
        self.logger.log_action("Text typed character-by-character", {
            "length": len(text),
            "typed": typed_count
        })
        
        return f"⌨️ Typed {typed_count} characters"
    
    # -------------------------------------------------------------------------
    # ⌨️ KEY PRESSES - ADVANCED
    # -------------------------------------------------------------------------
    
    async def press_key(self, key: str, hold_duration: float = 0.05) -> str:
        """
        Presses a single key with validation.
        
        Args:
            key: Key name (e.g., "enter", "space", "a", "f1")
            hold_duration: How long to hold the key
        
        Returns:
            Status message
        """
        if not self.is_active():
            return "🛑 Controller is inactive"
        
        if not self._ensure_controllers():
            return "❌ Controllers not initialized"
        
        # Validate key
        key_lower = key.lower()
        if key_lower not in self.special_keys_map and key_lower not in self.valid_keys:
            return f"❌ Invalid key: {key}. Valid keys: a-z, 0-9, enter, space, tab, esc, etc."
        
        try:
            k = self.special_keys_map.get(key_lower, key)
            
            self._keyboard.press(k)
            await asyncio.sleep(hold_duration)
            self._keyboard.release(k)
            
            self.logger.log_action("Key pressed", {"key": key})
            
            return f"⌨️ Key '{key}' pressed"
            
        except Exception as e:
            self.logger.log_error("Press key failed", e)
            return f"❌ Key press error: {str(e)}"
    
    async def press_hotkey(self, keys: List[str], 
                          hold_duration: float = 0.05) -> str:
        """
        Presses multiple keys as a hotkey combination.
        
        Args:
            keys: List of key names (e.g., ["ctrl", "c"])
            hold_duration: How long to hold keys
        
        Returns:
            Status message
        """
        if not self.is_active():
            return "🛑 Controller is inactive"
        
        if not self._ensure_controllers():
            return "❌ Controllers not initialized"
        
        if not keys or len(keys) < 1:
            return "❌ At least one key required"
        
        # Security validation
        valid, msg = SecurityValidator.validate_hotkey(keys)
        if not valid:
            return msg
        
        # Resolve all keys
        resolved_keys = []
        for k in keys:
            k_lower = k.lower()
            if k_lower not in self.special_keys_map and k_lower not in self.valid_keys:
                return f"❌ Invalid key: {k}"
            resolved_keys.append(self.special_keys_map.get(k_lower, k))
        
        try:
            # Press all keys in order
            for k in resolved_keys:
                self._keyboard.press(k)
                await asyncio.sleep(0.02)
            
            # Hold briefly
            await asyncio.sleep(hold_duration)
            
            # Release in reverse order
            for k in reversed(resolved_keys):
                self._keyboard.release(k)
                await asyncio.sleep(0.02)
            
            self.logger.log_action("Hotkey pressed", {"keys": keys})
            
            return f"⌨️ Hotkey {' + '.join(keys)} executed"
            
        except Exception as e:
            self.logger.log_error("Hotkey failed", e)
            return f"❌ Hotkey error: {str(e)}"
    
    async def hold_key(self, key: str, duration: float = 1.0) -> str:
        """
        🆕 NEW: Holds a key for specified duration.
        
        Args:
            key: Key to hold
            duration: Hold duration in seconds
        
        Returns:
            Status message
        """
        if not self.is_active():
            return "🛑 Controller is inactive"
        
        key_lower = key.lower()
        if key_lower not in self.special_keys_map and key_lower not in self.valid_keys:
            return f"❌ Invalid key: {key}"
        
        try:
            k = self.special_keys_map.get(key_lower, key)
            
            self._keyboard.press(k)
            await asyncio.sleep(duration)
            self._keyboard.release(k)
            
            self.logger.log_action("Key held", {"key": key, "duration": duration})
            
            return f"⌨️ Key '{key}' held for {duration}s"
            
        except Exception as e:
            self.logger.log_error("Hold key failed", e)
            return f"❌ Hold key error: {str(e)}"
    
    # -------------------------------------------------------------------------
    # 🔊 VOLUME CONTROL - ADVANCED
    # -------------------------------------------------------------------------
    
    async def control_volume(self, action: str) -> str:
        """
        Controls system volume with precise percentage support.
        
        Args:
            action: "up", "down", "mute", "50" (percentage), "full", "zero"
        
        Returns:
            Status message
        """
        if not self.is_active():
            return "🛑 Controller is inactive"
        
        action = action.lower().strip()
        
        try:
            # Handle percentage-based volume
            target_level = None
            
            if "full" in action or "100" in action:
                target_level = 100
            elif "half" in action or "50" in action:
                target_level = 50
            elif "zero" in action or "0" in action or "mute" == action:
                target_level = 0
            else:
                # Extract number from text
                match = re.search(r'(\d+)', action)
                if match:
                    target_level = int(match.group(1))
            
            if target_level is not None:
                target_level = max(0, min(100, target_level))
                
                # Reset volume to 0
                for _ in range(50):
                    self._pyautogui.press("volumedown")
                    await asyncio.sleep(0.01)
                
                # Set to target (assuming 2% per press)
                presses = target_level // 2
                for _ in range(presses):
                    self._pyautogui.press("volumeup")
                    await asyncio.sleep(0.01)
                
                self.logger.log_action("Volume set", {"target_percentage": target_level})
                return f"🔊 Volume set to approximately {target_level}%"
            
            # Handle directional commands
            if action == "up":
                for _ in range(5):
                    self._pyautogui.press("volumeup")
                return "🔊 Volume increased"
            elif action == "down":
                for _ in range(5):
                    self._pyautogui.press("volumedown")
                return "🔊 Volume decreased"
            elif action == "mute":
                self._pyautogui.press("volumemute")
                return "🔇 System muted/unmuted"
            
            return f"❌ Unknown volume action: {action}"
            
        except Exception as e:
            self.logger.log_error("Volume control failed", e)
            return f"❌ Volume control failed: {str(e)}"
    
    # -------------------------------------------------------------------------
    # 🎭 GESTURES - ADVANCED
    # -------------------------------------------------------------------------
    
    async def swipe_gesture(self, direction: str, 
                           distance: int = 200,
                           speed: str = "normal") -> str:
        """
        Performs swipe gesture for touch-like interactions.
        
        Args:
            direction: "up", "down", "left", "right"
            distance: Swipe distance in pixels
            speed: "slow", "normal", "fast"
        
        Returns:
            Status message
        """
        if not self.is_active():
            return "🛑 Controller is inactive"
        
        valid_directions = ["up", "down", "left", "right"]
        if direction.lower() not in valid_directions:
            return f"❌ Invalid direction: {direction}. Valid: {', '.join(valid_directions)}"
        
        try:
            screen_width, screen_height = self._get_screen_size()
            center_x, center_y = screen_width // 2, screen_height // 2
            
            # Calculate start and end positions
            if direction == "up":
                start = (center_x, center_y + distance)
                end = (center_x, center_y - distance)
            elif direction == "down":
                start = (center_x, center_y - distance)
                end = (center_x, center_y + distance)
            elif direction == "left":
                start = (center_x + distance, center_y)
                end = (center_x - distance, center_y)
            elif direction == "right":
                start = (center_x - distance, center_y)
                end = (center_x + distance, center_y)
            
            # Move to start position
            await self.move_cursor_to_position(start[0], start[1], speed="fast")
            await asyncio.sleep(0.1)
            
            # Press and drag
            self._mouse.press(self._pynput_button.left)
            
            speed_multiplier = {"slow": Config.SLOW_MODE_MULTIPLIER, "normal": 1.0, "fast": 0.5}
            duration = Config.GESTURE_DURATION * speed_multiplier.get(speed, 1.0)
            
            if Config.ENABLE_HUMANIZATION:
                self._pyautogui.dragTo(end[0], end[1], duration=duration,
                                      tween=self._pyautogui.easeInOutQuad)
            else:
                self._pyautogui.dragTo(end[0], end[1])
            
            # Release
            self._mouse.release(self._pynput_button.left)
            
            self.logger.log_action("Swipe gesture", {
                "direction": direction,
                "distance": distance
            })
            
            return f"🖱️ Swipe {direction} completed"
            
        except Exception as e:
            self.logger.log_error("Swipe gesture failed", e)
            return f"❌ Swipe error: {str(e)}"
    
    async def circle_gesture(self, radius: int = 50, 
                           direction: str = "clockwise",
                           duration: float = 1.0) -> str:
        """
        🆕 NEW: Performs circular gesture.
        
        Args:
            radius: Circle radius in pixels
            direction: "clockwise" or "counter-clockwise"
            duration: Gesture duration
        
        Returns:
            Status message
        """
        if not self.is_active():
            return "🛑 Controller is inactive"
        
        try:
            import math
            
            center_x, center_y = self._get_current_position()
            steps = 36  # 10 degrees per step
            
            self._mouse.press(self._pynput_button.left)
            
            for i in range(steps + 1):
                angle = (i / steps) * 2 * math.pi
                if direction == "counter-clockwise":
                    angle = -angle
                
                x = center_x + radius * math.cos(angle)
                y = center_y + radius * math.sin(angle)
                
                self._pyautogui.moveTo(int(x), int(y))
                await asyncio.sleep(duration / steps)
            
            self._mouse.release(self._pynput_button.left)
            
            self.logger.log_action("Circle gesture", {
                "radius": radius,
                "direction": direction
            })
            
            return f"🖱️ Circle gesture ({direction}) completed"
            
        except Exception as e:
            self.logger.log_error("Circle gesture failed", e)
            return f"❌ Circle gesture error: {str(e)}"
    
    # -------------------------------------------------------------------------
    # 📊 ANALYTICS & DIAGNOSTICS
    # -------------------------------------------------------------------------
    
    def get_movement_analytics(self) -> Dict:
        """🆕 NEW: Returns movement analytics."""
        if not self._movement_history:
            return {"total_movements": 0}
        
        total_distance = sum(m["distance"] for m in self._movement_history)
        avg_distance = total_distance / len(self._movement_history)
        
        return {
            "total_movements": len(self._movement_history),
            "total_distance_pixels": round(total_distance, 2),
            "average_distance_pixels": round(avg_distance, 2),
            "session_id": self.session_id
        }
    
    def reset_rate_limiters(self):
        """🆕 NEW: Resets all rate limiters."""
        self.click_limiter.reset()
        self.scroll_limiter.reset()
        self.keystroke_limiter.reset()
        self.logger.log_action("Rate limiters reset")
    
    def get_session_report(self) -> str:
        """🆕 NEW: Generates session report."""
        status = self.get_status()
        analytics = self.get_movement_analytics()
        
        report = f"""
📊 **Controller Session Report**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Session ID: {self.session_id}
Status: {'🟢 Active' if self.active else '🔴 Inactive'}
Uptime: {status['uptime_seconds']:.1f} seconds
Screen Size: {status['screen_size'][0]}x{status['screen_size'][1]}

📈 **Movement Analytics**
Total Movements: {analytics.get('total_movements', 0)}
Total Distance: {analytics.get('total_distance_pixels', 0):.0f} px
Average Distance: {analytics.get('average_distance_pixels', 0):.0f} px
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        return report


# =============================================================================
# 🎯 GLOBAL CONTROLLER INSTANCE
# =============================================================================

controller = AdvancedSafeController()


# =============================================================================
# 🔧 HELPER DECORATORS
# =============================================================================

@contextmanager
def controller_session(token: str = os.environ.get("SHELL_CTRL_TOKEN", "")):
    """Context manager for temporary controller activation."""
    controller.activate(token)
    try:
        yield controller
    finally:
        controller.deactivate()


def with_temporary_activation(fn):
    """Decorator for temporary activation during tool execution."""
    @wraps(fn)
    async def wrapper(*args, **kwargs):
        controller.activate(os.environ.get("SHELL_CTRL_TOKEN", ""))
        try:
            result = await fn(*args, **kwargs)
            await asyncio.sleep(0.5)
            return result
        finally:
            controller.deactivate()
    return wrapper


# =============================================================================
# LiveKit tool wrappers
# =============================================================================

# Try to import function_tool, provide fallback for standalone testing
try:
    from shell_safe_executor import god_tier_tool as function_tool
    FUNCTION_TOOL_AVAILABLE = True
except ImportError:
    FUNCTION_TOOL_AVAILABLE = False
    # Fallback decorator for testing
    def function_tool(func):
        return func

@function_tool
async def move_cursor_tool(direction: str, distance: int = 100, speed: str = "normal") -> str:
    """
    🖱️ Moves mouse cursor in specified direction with humanized movement.
    
    Args:
        direction: "up", "down", "left", "right", "up-left", "up-right", "down-left", "down-right"
        distance: Pixels to move (default: 100)
        speed: "slow", "normal", "fast" (default: "normal")
    
    Examples:
        - "Move mouse up 100 pixels"
        - "Move cursor down-right fast"
    """
    return await with_temporary_activation(controller.move_cursor)(direction, distance, speed)


@function_tool
async def move_cursor_to_position_tool(x: int, y: int, speed: str = "normal", smooth: bool = True) -> str:
    """
    Moves cursor to exact coordinates with optional smooth animation.
    
    Args:
        x: Target X coordinate (pixels from left)
        y: Target Y coordinate (pixels from top)
        speed: "slow", "normal", "fast"
        smooth: Enable smooth animation (default: True)
    
    Examples:
        - "Move cursor to position 500, 300"
        - "Click at coordinates 960, 540"
    """
    return await with_temporary_activation(controller.move_cursor_to_position)(x, y, speed, smooth)


@function_tool
async def move_cursor_to_element_tool(element_description: str) -> str:
    """
    👁️ AI-POWERED: Moves cursor to UI element using vision engine.
    
    Args:
        element_description: Description of element to find
    
    Examples:
        - "Move to submit button"
        - "Click on search box"
        - "Go to the login field"
    """
    return await with_temporary_activation(controller.move_cursor_to_element)(element_description)


@function_tool
async def mouse_click_tool(button: str = "left", count: int = 1) -> str:
    """
    🖱️ Performs mouse click(s).
    
    Args:
        button: "left", "right", "middle", "double", "triple"
        count: Number of clicks (1-5)
    
    Examples:
        - "Left click"
        - "Double click"
        - "Right click twice"
    """
    return await with_temporary_activation(controller.mouse_click)(button, count)


@function_tool
async def mouse_drag_tool(from_x: int, from_y: int, to_x: int, to_y: int, duration: float = 0.5) -> str:
    """
    🖱️ Performs drag operation from one position to another.
    
    Args:
        from_x, from_y: Start position coordinates
        to_x, to_y: End position coordinates
        duration: Drag duration in seconds
    
    Examples:
        - "Drag from 100,100 to 500,500"
        - "Move file from top-left to bottom-right"
    """
    return await with_temporary_activation(controller.mouse_drag)(from_x, from_y, to_x, to_y, duration)


@function_tool
async def scroll_cursor_tool(direction: str, amount: int = 10, smooth: bool = True) -> str:
    """
    📜 Scrolls in specified direction.
    
    Args:
        direction: "up", "down", "left", "right"
        amount: Scroll amount (default: 10)
        smooth: Enable smooth scrolling (default: True)
    
    Examples:
        - "Scroll down"
        - "Scroll up 20 units"
        - "Scroll right slowly"
    """
    return await with_temporary_activation(controller.scroll_cursor)(direction, amount, smooth)


@function_tool
async def type_text_tool(text: str, use_clipboard: bool = True) -> str:
    """
    ⌨️ Types text with smart clipboard fallback.
    
    Args:
        text: Text to type
        use_clipboard: Use clipboard for long text (default: True)
    
    Examples:
        - "Type 'Hello World'"
        - "Paste this code: def hello():..."
        - "Type the email content"
    """
    return await with_temporary_activation(controller.type_text)(text, use_clipboard)


@function_tool
async def press_key_tool(key: str) -> str:
    """
    ⌨️ Presses a single key.
    
    Args:
        key: Key name (e.g., "enter", "space", "tab", "esc", "f1", "a")
    
    Examples:
        - "Press enter"
        - "Press F5 to refresh"
        - "Press escape"
    """
    return await with_temporary_activation(controller.press_key)(key)


@function_tool
async def press_hotkey_tool(keys: List[str]) -> str:
    """
    ⌨️ Presses multiple keys as hotkey combination.
    
    Args:
        keys: List of key names
    
    Examples:
        - "Press Ctrl+C"
        - "Press Alt+Tab"
        - "Press Ctrl+Shift+Esc"
    """
    return await with_temporary_activation(controller.press_hotkey)(keys)


@function_tool
async def hold_key_tool(key: str, duration: float = 1.0) -> str:
    """
    ⌨️ Holds a key for specified duration.
    
    Args:
        key: Key to hold
        duration: Hold duration in seconds
    
    Examples:
        - "Hold space for 2 seconds"
        - "Keep pressing shift"
    """
    return await with_temporary_activation(controller.hold_key)(key, duration)


@function_tool
async def control_volume_tool(action: str) -> str:
    """
    🔊 Controls system volume.
    
    Args:
        action: "up", "down", "mute", "50" (percentage), "full", "zero"
    
    Examples:
        - "Increase volume"
        - "Set volume to 50%"
        - "Mute the system"
        - "Full volume"
    """
    return await with_temporary_activation(controller.control_volume)(action)


@function_tool
async def swipe_gesture_tool(direction: str, distance: int = 200) -> str:
    """
    🖱️ Performs swipe gesture (touch-like interaction).
    
    Args:
        direction: "up", "down", "left", "right"
        distance: Swipe distance in pixels
    
    Examples:
        - "Swipe up"
        - "Swipe left to go back"
        - "Swipe down to refresh"
    """
    return await with_temporary_activation(controller.swipe_gesture)(direction, distance)


@function_tool
async def circle_gesture_tool(radius: int = 50, direction: str = "clockwise") -> str:
    """
    🆕 NEW: Performs circular gesture.
    
    Args:
        radius: Circle radius in pixels
        direction: "clockwise" or "counter-clockwise"
    
    Examples:
        - "Draw a circle"
        - "Make a counter-clockwise circle"
    """
    return await with_temporary_activation(controller.circle_gesture)(radius, direction)


@function_tool
async def paste_from_clipboard_tool() -> str:
    """
    📋 Pastes text from clipboard (Ctrl+V).
    
    Examples:
        - "Paste here"
        - "Paste the copied text"
    """
    return await with_temporary_activation(controller.press_hotkey)(["ctrl", "v"])


@function_tool
async def get_controller_status_tool() -> str:
    """
    🆕 NEW: Returns current controller status and analytics.
    
    Examples:
        - "What's the controller status?"
        - "Show movement analytics"
    """
    status = controller.get_status()
    analytics = controller.get_movement_analytics()
    
    return f"""
🖱️ **Controller Status**
Active: {status['active']}
Session: {status['session_id']}
Position: {status['last_position']}
Screen: {status['screen_size'][0]}x{status['screen_size'][1]}

📈 **Analytics**
Movements: {analytics.get('total_movements', 0)}
Distance: {analytics.get('total_distance_pixels', 0):.0f} px
"""


@function_tool
async def reset_controller_rate_limits_tool() -> str:
    """
    🆕 NEW: Resets all rate limiters.
    Use when rate limiting is preventing actions.
    
    Examples:
        - "Reset rate limits"
        - "Clear controller limits"
    """
    controller.reset_rate_limiters()
    return "✅ Rate limiters reset successfully"


@function_tool
async def get_session_report_tool() -> str:
    """
    🆕 NEW: Generates detailed session report.
    
    Examples:
        - "Show session report"
        - "Generate activity report"
    """
    return controller.get_session_report()


# =============================================================================
# 🎮 MOUSE GESTURE TOOL - Advanced Mouse Gestures
# =============================================================================

@function_tool
async def mouse_gesture_tool(gesture: str, duration: float = 0.5) -> str:
    """
    🎮 Mouse gesture tool - Common mouse gestures perform karta hai.

    Supported gestures:
        - 'circle': Current position pe ek circle draw karta hai
        - 'zigzag': Zigzag pattern mein cursor move karta hai
        - 'shake': Cursor ko left-right rapidly shake karta hai (visual effect)
        - 'spiral': Current position se bahar ki taraf spiral movement

    Args:
        gesture: Gesture type - "circle", "zigzag", "shake", "spiral"
        duration: Total duration of gesture in seconds (default: 0.5)

    Examples:
        - "Draw a circle with mouse"
        - "Shake the cursor"
        - "Do a spiral gesture"
        - "Zigzag mouse movement karo"
    """
    try:
        import pyautogui
        import math

        gesture = gesture.lower().strip()
        valid_gestures = ['circle', 'zigzag', 'shake', 'spiral']

        if gesture not in valid_gestures:
            return f"❌ Invalid gesture '{gesture}'. Valid options: {', '.join(valid_gestures)}"

        start_x, start_y = pyautogui.position()
        steps = 36  # Number of steps for smooth movement
        step_delay = max(0.01, duration / steps)

        if gesture == 'circle':
            radius = 60
            for i in range(steps + 1):
                angle = (2 * math.pi * i) / steps
                target_x = int(start_x + radius * math.cos(angle))
                target_y = int(start_y + radius * math.sin(angle))
                pyautogui.moveTo(target_x, target_y, duration=step_delay)
            # Wapas original position pe aao
            pyautogui.moveTo(start_x, start_y, duration=0.05)
            return f"✅ Circle gesture complete! 🔵 Position ({start_x}, {start_y}) pe radius {radius}px ka circle draw hua."

        elif gesture == 'zigzag':
            zigzag_width = 80
            zigzag_height = 30
            num_zags = 5
            step_delay = max(0.01, duration / num_zags)
            for i in range(num_zags):
                direction = 1 if i % 2 == 0 else -1
                target_x = start_x + (direction * zigzag_width)
                target_y = start_y + (i * zigzag_height)
                pyautogui.moveTo(target_x, target_y, duration=step_delay)
            pyautogui.moveTo(start_x, start_y, duration=0.05)
            return f"✅ Zigzag gesture complete! ⚡ {num_zags} zags perform hue width={zigzag_width}px."

        elif gesture == 'shake':
            shake_distance = 30
            num_shakes = 8
            step_delay = max(0.01, duration / (num_shakes * 2))
            for i in range(num_shakes):
                pyautogui.moveTo(start_x + shake_distance, start_y, duration=step_delay)
                pyautogui.moveTo(start_x - shake_distance, start_y, duration=step_delay)
            pyautogui.moveTo(start_x, start_y, duration=0.05)
            return f"✅ Shake gesture complete! 🫨 Cursor ko {num_shakes} baar shake kiya left-right."

        elif gesture == 'spiral':
            max_radius = 80
            total_rotations = 3
            for i in range(steps + 1):
                progress = i / steps
                current_radius = max_radius * progress
                angle = 2 * math.pi * total_rotations * progress
                target_x = int(start_x + current_radius * math.cos(angle))
                target_y = int(start_y + current_radius * math.sin(angle))
                pyautogui.moveTo(target_x, target_y, duration=step_delay)
            pyautogui.moveTo(start_x, start_y, duration=0.05)
            return f"✅ Spiral gesture complete! 🌀 {total_rotations} rotations ke saath {max_radius}px tak spiral hua."

    except ImportError:
        return "❌ pyautogui module install nahi hai. `pip install pyautogui` run karo."
    except Exception as e:
        return f"❌ Gesture error: {str(e)}"


# =============================================================================
# 🖱️ MULTI CLICK TOOL - Multiple Clicks at Position
# =============================================================================

@function_tool
async def multi_click_tool(x: int, y: int, clicks: int = 2, interval: float = 0.1) -> str:
    """
    🖱️ Multiple clicks ek position pe - double-click, triple-click ya custom rapid clicks.

    Args:
        x: X coordinate (pixels from left)
        y: Y coordinate (pixels from top)
        clicks: Kitne clicks karne hain (default: 2 for double-click)
        interval: Clicks ke beech mein interval seconds mein (default: 0.1)

    Use cases:
        - clicks=2: Double-click - word select karta hai
        - clicks=3: Triple-click - poora paragraph/line select karta hai
        - clicks=5+: Rapid clicking for special interactions

    Examples:
        - "Double click at 500, 300"
        - "Triple click to select paragraph"
        - "5 baar click karo position 200, 400 pe"
    """
    try:
        import pyautogui

        # Validate coordinates
        valid, msg = SecurityValidator.validate_coordinates(x, y)
        if not valid:
            return msg

        if clicks < 1 or clicks > 20:
            return "❌ Clicks 1 se 20 ke beech hone chahiye. Zyada clicks allowed nahi hai."

        if interval < 0.01 or interval > 2.0:
            return "❌ Interval 0.01s se 2.0s ke beech hona chahiye."

        # Pehle cursor ko position pe le jao smoothly
        pyautogui.moveTo(x, y, duration=Config.MOUSE_MOVE_DURATION)
        await asyncio.sleep(0.05)

        # Ab clicks perform karo
        pyautogui.click(x=x, y=y, clicks=clicks, interval=interval)

        click_type = "Double-click" if clicks == 2 else "Triple-click" if clicks == 3 else f"{clicks}x click"
        return (
            f"✅ {click_type} complete! 🖱️ Position ({x}, {y}) pe {clicks} clicks "
            f"perform hue interval={interval}s ke saath."
        )

    except ImportError:
        return "❌ pyautogui module install nahi hai. `pip install pyautogui` run karo."
    except Exception as e:
        return f"❌ Multi-click error: {str(e)}"


# =============================================================================
# ⌨️ KEYBOARD MACRO TOOL - Record & Playback Macros
# =============================================================================

# Macro storage file path
MACRO_STORAGE_FILE = Path(__file__).parent / "shell_macros.json"

def _load_macros() -> Dict:
    """Macros ko JSON file se load karta hai."""
    try:
        if MACRO_STORAGE_FILE.exists():
            with open(MACRO_STORAGE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logging.warning(f"Macro file load error: {e}")
    return {}

def _save_macros(macros: Dict) -> bool:
    """Macros ko JSON file mein save karta hai."""
    try:
        with open(MACRO_STORAGE_FILE, 'w', encoding='utf-8') as f:
            json.dump(macros, f, indent=2, ensure_ascii=False)
        return True
    except IOError as e:
        logging.error(f"Macro file save error: {e}")
        return False

@function_tool
async def keyboard_macro_tool(action: str, macro_name: str = "", keys: str = "") -> str:
    """
    ⌨️ Keyboard macros record aur playback karta hai. Repetitive key sequences save karo aur replay karo.

    Args:
        action: "record", "play", "list", "delete"
            - record: Naya macro save karta hai (macro_name aur keys required)
            - play: Saved macro playback karta hai (macro_name required)
            - list: Saare saved macros dikhata hai
            - delete: Ek macro delete karta hai (macro_name required)
        macro_name: Macro ka naam (record/play/delete ke liye required)
        keys: Space-separated key sequence for recording
              Example: "ctrl+c down down ctrl+v" ya "hello enter"
              Modifiers: ctrl+key, alt+key, shift+key, win+key

    Examples:
        - "Record macro 'copy_paste' with keys 'ctrl+c ctrl+v'"
        - "Play macro 'copy_paste'"
        - "List all saved macros"
        - "Delete macro 'old_macro'"
    """
    try:
        import pyautogui

        action = action.lower().strip()
        valid_actions = ['record', 'play', 'list', 'delete']

        if action not in valid_actions:
            return f"❌ Invalid action '{action}'. Valid: {', '.join(valid_actions)}"

        # ---- LIST ACTION ----
        if action == 'list':
            macros = _load_macros()
            if not macros:
                return "📋 Koi saved macro nahi hai abhi. 'record' action se naya macro banao!"

            lines = ["📋 **Saved Macros:**\n"]
            for name, data in macros.items():
                key_seq = data.get('keys', '')
                created = data.get('created', 'unknown')
                lines.append(f"  🔹 **{name}**: `{key_seq}` (saved: {created})")
            return "\n".join(lines)

        # ---- RECORD ACTION ----
        elif action == 'record':
            if not macro_name:
                return "❌ Macro name dena zaroori hai! Example: macro_name='my_macro'"
            if not keys:
                return "❌ Keys sequence dena zaroori hai! Example: keys='ctrl+c down down ctrl+v'"

            # Validate macro name (alphanumeric + underscore only)
            if not re.match(r'^[a-zA-Z0-9_]+$', macro_name):
                return "❌ Macro name mein sirf letters, numbers aur underscore allowed hai."

            macros = _load_macros()
            macros[macro_name] = {
                'keys': keys,
                'created': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'play_count': 0
            }

            if _save_macros(macros):
                return (
                    f"✅ Macro '{macro_name}' successfully record hua! ⌨️\n"
                    f"   Keys: `{keys}`\n"
                    f"   Playback ke liye: action='play', macro_name='{macro_name}'"
                )
            else:
                return "❌ Macro save karne mein error aa gaya. File write permission check karo."

        # ---- PLAY ACTION ----
        elif action == 'play':
            if not macro_name:
                return "❌ Macro name dena zaroori hai! Pehle 'list' se available macros dekho."

            macros = _load_macros()
            if macro_name not in macros:
                available = ', '.join(macros.keys()) if macros else 'koi nahi'
                return f"❌ Macro '{macro_name}' nahi mila. Available macros: {available}"

            key_sequence = macros[macro_name]['keys']
            key_parts = key_sequence.split()

            executed_keys = []
            for key_part in key_parts:
                key_part = key_part.strip()
                if not key_part:
                    continue

                if '+' in key_part:
                    # Hotkey combo like ctrl+c, alt+tab
                    combo_keys = key_part.split('+')
                    pyautogui.hotkey(*combo_keys)
                    executed_keys.append(key_part)
                else:
                    # Single key ya text
                    # Check if it's a special key
                    special_keys = [
                        'enter', 'tab', 'escape', 'space', 'backspace', 'delete',
                        'up', 'down', 'left', 'right', 'home', 'end',
                        'pageup', 'pagedown', 'f1', 'f2', 'f3', 'f4', 'f5',
                        'f6', 'f7', 'f8', 'f9', 'f10', 'f11', 'f12',
                        'capslock', 'numlock', 'printscreen', 'insert',
                        'volumeup', 'volumedown', 'volumemute'
                    ]
                    if key_part.lower() in special_keys:
                        pyautogui.press(key_part.lower())
                    else:
                        pyautogui.typewrite(key_part, interval=0.02)
                    executed_keys.append(key_part)

                await asyncio.sleep(0.05)  # Chota sa delay between keys

            # Update play count
            macros[macro_name]['play_count'] = macros[macro_name].get('play_count', 0) + 1
            _save_macros(macros)

            return (
                f"✅ Macro '{macro_name}' successfully play hua! 🎬\n"
                f"   Executed: {' -> '.join(executed_keys)}\n"
                f"   Total plays: {macros[macro_name]['play_count']}"
            )

        # ---- DELETE ACTION ----
        elif action == 'delete':
            if not macro_name:
                return "❌ Macro name dena zaroori hai jo delete karna hai."

            macros = _load_macros()
            if macro_name not in macros:
                return f"❌ Macro '{macro_name}' exist nahi karta."

            del macros[macro_name]
            if _save_macros(macros):
                return f"✅ Macro '{macro_name}' successfully delete ho gaya! 🗑️"
            else:
                return "❌ Macro delete karne mein error. File permission check karo."

    except ImportError:
        return "❌ pyautogui module install nahi hai. `pip install pyautogui` run karo."
    except Exception as e:
        return f"❌ Macro error: {str(e)}"


# =============================================================================
# 🎯 MAIN (FOR TESTING)
# =============================================================================

if __name__ == "__main__":
    # Fix Windows console encoding for emojis
    import sys
    if sys.platform == 'win32':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass
    
    print("[KEYBOARD_MOUSE_CTRL] Test Mode")
    print("=" * 60)

    async def test_controller():
        # Activate
        success, msg = controller.activate(os.environ.get("SHELL_CTRL_TOKEN", ""))
        print(f"Activation: {msg}")

        if success:
            # Test movement
            print("\n[TEST] Testing movement...")
            result = await controller.move_cursor("right", 100)
            print(result)

            await asyncio.sleep(0.5)

            result = await controller.move_cursor_to_position(500, 300)
            print(result)

            # Test typing
            print("\n[TEST] Testing typing...")
            result = await controller.type_text("Hello from Shell AI!")
            print(result)

            # Test status
            print("\n[TEST] Status Report:")
            print(controller.get_session_report())

            # Deactivate
            print("\n" + controller.deactivate())
            
            print("\n[TEST] All tests completed!")
        else:
            print("[ERROR] Activation failed!")

    asyncio.run(test_controller())
