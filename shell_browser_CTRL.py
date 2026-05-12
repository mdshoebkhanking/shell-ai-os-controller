#!/usr/bin/env python3
# =============================================================================
# Shell browser automation controller
# =============================================================================
# Advanced Browser Automation with:
# - ✅ Multi-Browser Support (Chrome, Edge, Firefox, Brave)
# - ✅ AI-Powered Web Navigation
# - ✅ Smart Tab Management
# - YouTube automation
# - Web AI integration when providers are configured
# - Visual intelligence and OCR hooks
# - Form filling and submission
# - Screenshot and annotation
# - Download management
# - Cookie and session handling
# - Reading mode, translation, price tracking, and news workflows
# - ✅ Social Media Automation
# - ✅ Security & Privacy Controls
# =============================================================================

import os
import sys
import webbrowser
import urllib.parse
import urllib.request
import asyncio
import time
import logging
import json
import re
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any
from functools import wraps, lru_cache
from dataclasses import dataclass, field, asdict
from enum import Enum
import threading
from collections import deque
from shell_logger import get_logger

logger = get_logger("shell_browser_ctrl")

# Selenium for advanced automation
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    logger.warning("Selenium not installed. Install: pip install selenium")

# PIL for screenshots
try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# PyAutoGUI for automation
try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False

# Pyperclip for clipboard
try:
    import pyperclip
    PYPERCLIP_AVAILABLE = True
except ImportError:
    PYPERCLIP_AVAILABLE = False

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

# =============================================================================
# 📊 CONFIGURATION
# =============================================================================

class Config:
    """Browser configuration."""
    
    # Default Browser
    DEFAULT_BROWSER = "chrome"  # chrome, edge, firefox, brave
    
    # Browser Paths (Windows)
    BROWSER_PATHS = {
        "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        "edge": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        "firefox": r"C:\Program Files\Mozilla Firefox\firefox.exe",
        "brave": r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
    }
    
    # Timeout Settings
    PAGE_LOAD_TIMEOUT = 30
    ELEMENT_TIMEOUT = 10
    SCRIPT_TIMEOUT = 15
    
    # Screenshot Settings
    SCREENSHOT_DIR = "Pictures/Shell_Screenshots"
    SCREENSHOT_FORMAT = "png"
    SCREENSHOT_QUALITY = 95
    
    # Download Settings
    DOWNLOAD_DIR = "Downloads/Shell_Downloads"
    
    # AI Platforms
    AI_PLATFORMS = {
        "chatgpt": "https://chatgpt.com/",
        "gemini": "https://gemini.google.com/app",
        "claude": "https://claude.ai/new",
        "perplexity": "https://www.perplexity.ai/",
        "copilot": "https://copilot.microsoft.com/",
    }
    
    # Social Media
    SOCIAL_PLATFORMS = {
        "twitter": "https://twitter.com/",
        "facebook": "https://facebook.com/",
        "instagram": "https://instagram.com/",
        "linkedin": "https://linkedin.com/",
        "reddit": "https://reddit.com/",
    }
    
    # Rate Limiting
    MAX_REQUESTS_PER_MINUTE = 30
    MAX_TABS = 20
    
    # Logging
    LOG_FILE = "shell_browser_ctrl.log"
    
    # Security
    BLOCKED_DOMAINS = [
        "malware", "phishing", "scam",
    ]


# =============================================================================
# 🎯 DATA CLASSES
# =============================================================================

@dataclass
class BrowserState:
    """Current browser state."""
    browser_name: str
    current_url: str
    title: str
    tab_count: int
    is_fullscreen: bool
    last_activity: datetime
    cookies_count: int


@dataclass
class TabInfo:
    """Tab information."""
    index: int
    title: str
    url: str
    is_active: bool
    favicon: Optional[str] = None


@dataclass
class DownloadInfo:
    """Download tracking."""
    filename: str
    url: str
    size: int
    status: str  # downloading, completed, failed
    timestamp: datetime


@dataclass
class AutomationAction:
    """Automation action record."""
    action_type: str
    target: str
    value: Optional[str]
    timestamp: datetime
    success: bool
    error: Optional[str] = None


# =============================================================================
# 🛡️ SECURITY VALIDATOR
# =============================================================================

class BrowserSecurityValidator:
    """Validates URLs and actions for security."""
    
    @classmethod
    def validate_url(cls, url: str) -> Tuple[bool, str]:
        """Validates URL for safety."""
        if not url:
            return False, "❌ URL cannot be empty"
        
        if len(url) > 2048:
            return False, "❌ URL too long"
        
        # Check blocked domains
        url_lower = url.lower()
        for blocked in Config.BLOCKED_DOMAINS:
            if blocked in url_lower:
                return False, f"⚠️ Blocked domain: {blocked}"
        
        # Validate URL format
        if not re.match(r'^https?://', url):
            url = "https://" + url
        
        return True, url
    
    @classmethod
    def validate_script(cls, script: str) -> Tuple[bool, str]:
        """Validates JavaScript for safety."""
        if not script:
            return False, "❌ Script cannot be empty"
        
        # Block dangerous operations
        dangerous_patterns = [
            r'alert\s*\(',
            r'confirm\s*\(',
            r'prompt\s*\(',
            r'window\.location\s*=',
            r'document\.write',
            r'eval\s*\(',
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, script, re.IGNORECASE):
                return False, f"⚠️ Dangerous operation blocked"
        
        return True, "OK"


# =============================================================================
# 📊 BROWSER ANALYTICS
# =============================================================================

class BrowserAnalytics:
    """Tracks browser usage analytics."""
    
    def __init__(self):
        self.history_file = Path("shell_browser_history.json")
        self.sessions: List[Dict] = self._load_history()
    
    def _load_history(self) -> List[Dict]:
        """Loads history from file."""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logging.getLogger("browser_analytics").warning(f"History load failed: {e}")
                return []
        return []

    def _save_history(self):
        """Saves history to file."""
        try:
            with open(self.history_file, 'w') as f:
                json.dump(self.sessions, f, indent=2, default=str)
        except OSError as e:
            logging.getLogger("browser_analytics").warning(f"History save failed: {e}")
    
    def log_action(self, action: str, url: str = "", details: Dict = None):
        """Logs browser action."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "url": url,
            "details": details or {}
        }
        self.sessions.insert(0, entry)
        
        # Trim if too long
        if len(self.sessions) > 1000:
            self.sessions = self.sessions[-1000:]
        
        self._save_history()
    
    def get_stats(self) -> Dict:
        """Returns usage statistics."""
        if not self.sessions:
            return {"total_actions": 0}
        
        # Action breakdown
        actions = {}
        for entry in self.sessions:
            action = entry.get('action', 'unknown')
            actions[action] = actions.get(action, 0) + 1
        
        # Domain breakdown
        domains = {}
        for entry in self.sessions:
            url = entry.get('url', '')
            if url:
                try:
                    domain = urllib.parse.urlparse(url).netloc
                    domains[domain] = domains.get(domain, 0) + 1
                except Exception as _e:
                    logger.debug("ignored Exception: %s", _e)
        # Count recent sessions safely
        recent_count = 0
        for e in self.sessions:
            try:
                ts = datetime.fromisoformat(e.get('timestamp', ''))
                if datetime.now() - ts < timedelta(hours=24):
                    recent_count += 1
            except (ValueError, TypeError):
                pass

        return {
            "total_actions": len(self.sessions),
            "action_breakdown": actions,
            "top_domains": dict(sorted(domains.items(), key=lambda x: x[1], reverse=True)[:10]),
            "recent_sessions": recent_count
        }
    
    def search_history(self, query: str) -> List[Dict]:
        """Searches browsing history."""
        query_lower = query.lower()
        return [
            e for e in self.sessions
            if query_lower in e.get('url', '').lower() or
               query_lower in e.get('action', '').lower()
        ]
    
    def clear_history(self):
        """Clears browsing history."""
        self.sessions.clear()
        self._save_history()


# =============================================================================
# 🌐 BROWSER CONTROLLER
# =============================================================================

class BrowserController:
    """Advanced browser automation controller."""
    
    def __init__(self):
        self.driver = None
        self.browser_name = Config.DEFAULT_BROWSER
        self.analytics = BrowserAnalytics()
        self.state: Optional[BrowserState] = None
        self.logger = logging.getLogger("browser_controller")
    
    def setup_driver(self, browser: str = None, headless: bool = False) -> bool:
        """Sets up Selenium WebDriver."""
        if not SELENIUM_AVAILABLE:
            self.logger.warning("Selenium not available")
            return False
        
        browser = browser or self.browser_name
        
        try:
            options = Options()
            options.add_argument("--start-maximized")
            
            if headless:
                options.add_argument("--headless")
            
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            
            # Set download preferences
            prefs = {
                "download.default_directory": str(Path.home() / Config.DOWNLOAD_DIR),
                "download.prompt_for_download": False,
                "plugins.always_open_pdf_externally": True,
            }
            options.add_experimental_option("prefs", prefs)
            
            self.driver = webdriver.Chrome(options=options)
            self.driver.set_page_load_timeout(Config.PAGE_LOAD_TIMEOUT)
            
            self.browser_name = browser
            self.logger.info(f"✅ Browser initialized: {browser}")
            return True
            
        except Exception as e:
            self.logger.error(f"Browser setup failed: {e}")
            return False
    
    def get_state(self) -> BrowserState:
        """Gets current browser state."""
        if not self.driver:
            return BrowserState(
                browser_name="",
                current_url="",
                title="",
                tab_count=0,
                is_fullscreen=False,
                last_activity=datetime.now(),
                cookies_count=0
            )
        
        try:
            return BrowserState(
                browser_name=self.browser_name,
                current_url=self.driver.current_url,
                title=self.driver.title,
                tab_count=len(self.driver.window_handles),
                is_fullscreen=False,  # Can't detect easily
                last_activity=datetime.now(),
                cookies_count=len(self.driver.get_cookies())
            )
        except Exception as e:
            self.logger.error(f"Failed to get browser state: {e}")
            return BrowserState("", "", "", 0, False, datetime.now(), 0)
    
    def navigate_to(self, url: str) -> Tuple[bool, str]:
        """Navigates to URL."""
        valid, result = BrowserSecurityValidator.validate_url(url)
        if not valid:
            return False, result
        
        url = result
        
        if not self.driver:
            webbrowser.open(url)
            self.analytics.log_action("open_url", url)
            return True, f"✅ Opened in default browser: {url}"
        
        try:
            self.driver.get(url)
            self.analytics.log_action("navigate", url)
            return True, f"✅ Navigated to: {url}"
        except Exception as e:
            return False, f"❌ Navigation failed: {e}"
    
    def take_screenshot(self, filename: str = None) -> Optional[str]:
        """Takes screenshot."""
        if not self.driver:
            return None
        
        try:
            home = os.path.expanduser("~")
            target_dir = os.path.join(home, Config.SCREENSHOT_DIR)
            Path(target_dir).mkdir(parents=True, exist_ok=True)
            
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"shell_browser_{timestamp}.{Config.SCREENSHOT_FORMAT}"
            
            filepath = os.path.join(target_dir, filename)
            
            self.driver.save_screenshot(filepath)
            
            self.analytics.log_action("screenshot", self.driver.current_url)
            self.logger.info(f"📸 Screenshot saved: {filepath}")
            
            return filepath
            
        except Exception as e:
            self.logger.error(f"Screenshot failed: {e}")
            return None
    
    def execute_script(self, script: str) -> Optional[Any]:
        """Executes JavaScript safely."""
        valid, msg = BrowserSecurityValidator.validate_script(script)
        if not valid:
            self.logger.warning(f"Script blocked: {msg}")
            return None
        
        if not self.driver:
            return None
        
        try:
            result = self.driver.execute_script(script)
            self.analytics.log_action("execute_script", self.driver.current_url, {"script": script[:50]})
            return result
        except Exception as e:
            self.logger.error(f"Script execution failed: {e}")
            return None
    
    def get_page_content(self) -> str:
        """Gets page HTML content."""
        if not self.driver:
            return ""
        
        try:
            return self.driver.page_source
        except Exception as e:
            self.logger.error(f"Failed to get page content: {e}")
            return ""
    
    def find_element(self, selector: str, by: str = "css") -> Optional[Any]:
        """Finds element on page."""
        if not self.driver:
            return None
        
        try:
            by_map = {
                "css": By.CSS_SELECTOR,
                "xpath": By.XPATH,
                "id": By.ID,
                "class": By.CLASS_NAME,
                "name": By.NAME,
            }
            
            wait = WebDriverWait(self.driver, Config.ELEMENT_TIMEOUT)
            element = wait.until(
                EC.presence_of_element_located((by_map.get(by, By.CSS_SELECTOR), selector))
            )
            return element
        except Exception as e:
            self.logger.debug(f"Element not found ({selector}): {e}")
            return None

    def click_element(self, selector: str, by: str = "css") -> bool:
        """Clicks element."""
        element = self.find_element(selector, by)
        if not element:
            return False
        
        try:
            element.click()
            self.analytics.log_action("click", self.driver.current_url, {"selector": selector})
            return True
        except Exception as e:
            self.logger.error(f"Click failed on {selector}: {e}")
            return False

    def fill_form(self, selector: str, value: str, by: str = "css") -> bool:
        """Fills form field."""
        element = self.find_element(selector, by)
        if not element:
            return False
        
        try:
            element.clear()
            element.send_keys(value)
            self.analytics.log_action("fill_form", self.driver.current_url, {"field": selector})
            return True
        except Exception as e:
            self.logger.error(f"Fill form failed on {selector}: {e}")
            return False

    def get_cookies(self) -> List[Dict]:
        """Gets all cookies."""
        if not self.driver:
            return []
        
        try:
            return self.driver.get_cookies()
        except Exception as e:
            self.logger.error(f"Failed to get cookies: {e}")
            return []
    
    def add_cookie(self, cookie: Dict) -> bool:
        """Adds cookie."""
        if not self.driver:
            return False
        
        try:
            self.driver.add_cookie(cookie)
            return True
        except Exception as e:
            self.logger.error(f"Failed to add cookie: {e}")
            return False
    
    def close(self):
        """Closes browser."""
        if self.driver:
            try:
                self.driver.quit()
                self.driver = None
                self.logger.info("Browser closed")
            except Exception as e:
                self.logger.error(f"Error closing browser: {e}")
                self.driver = None


# =============================================================================
# 🌍 GLOBAL INSTANCES
# =============================================================================

logger = logging.getLogger("shell_browser_ctrl")
controller = BrowserController()
analytics = BrowserAnalytics()


# =============================================================================
# 🚀 TOOL WRAPPERS
# =============================================================================

if not FUNCTION_TOOL_AVAILABLE:
    def function_tool(func):
        return func


@function_tool
async def open_browser_url(url: str) -> str:
    """
    🌐 Opens URL in default browser (or Selenium if available).
    Supports common shortcuts like 'google', 'youtube', 'github', 'gmail'.

    Args:
        url: Website URL or shortcut name

    Examples:
        - "Open google.com"
        - "Navigate to https://github.com"
        - "Open youtube"
        - "Open gmail"
    """
    try:
        # Common URL shortcuts
        URL_SHORTCUTS = {
            "google": "https://www.google.com",
            "youtube": "https://www.youtube.com",
            "github": "https://www.github.com",
            "gmail": "https://mail.google.com",
            "twitter": "https://twitter.com",
            "facebook": "https://www.facebook.com",
            "instagram": "https://www.instagram.com",
            "linkedin": "https://www.linkedin.com",
            "reddit": "https://www.reddit.com",
            "stackoverflow": "https://stackoverflow.com",
            "chatgpt": "https://chatgpt.com",
            "whatsapp": "https://web.whatsapp.com",
            "amazon": "https://www.amazon.com",
            "netflix": "https://www.netflix.com",
            "spotify": "https://open.spotify.com",
        }

        # Check if url is a shortcut
        url_lower = url.strip().lower()
        if url_lower in URL_SHORTCUTS:
            original_input = url
            url = URL_SHORTCUTS[url_lower]
            logger.info(f"🔗 Shortcut '{original_input}' -> {url}")

        valid, result = BrowserSecurityValidator.validate_url(url)
        if not valid:
            return result

        url = result

        # Try Selenium first if available
        if SELENIUM_AVAILABLE and controller.driver:
            success, msg = controller.navigate_to(url)
            return msg

        # Fallback to webbrowser
        webbrowser.open(url)
        analytics.log_action("open_url", url)
        logger.info(f"🌐 Opened: {url}")

        return f"✅ Browser mein {url} open kar diya hai Sir! Full URL: {url}"

    except Exception as e:
        logger.error(f"Error: {e}")
        return f"❌ URL open karne mein error: {str(e)}"


@function_tool
async def search_google(query: str) -> str:
    """
    🔍 Performs Google search.
    
    Args:
        query: Search term
    
    Examples:
        - "Search for Python tutorials"
        - "Google best restaurants near me"
    """
    try:
        encoded = urllib.parse.quote(query)
        url = f"https://www.google.com/search?q={encoded}"
        
        webbrowser.open(url)
        analytics.log_action("google_search", url, {"query": query})
        
        return f"✅ Google par '{query}' search kar diya hai Sir!"
        
    except Exception as e:
        return f"❌ Search error: {str(e)}"


# Module-level cache of the most recent YouTube search so play_youtube_video
# can open a specific result deterministically, without vision/click hacks.
# Structure: {"query": str, "ids": [str], "titles": [str]}
_YT_LAST_SEARCH: Dict[str, Any] = {"query": "", "ids": [], "titles": []}


async def _youtube_search_scrape(query: str, limit: int = 10) -> Tuple[List[str], List[str]]:
    """Scrape YouTube results page for top video IDs + titles.

    Uses the `ytInitialData` blob embedded in the HTML — stable, no API key
    needed, no browser automation. Runs blocking urllib in a thread.
    """
    def _fetch() -> str:
        encoded = urllib.parse.quote(query)
        url = f"https://www.youtube.com/results?search_query={encoded}"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0 Safari/537.36"
                ),
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.read().decode("utf-8", errors="ignore")

    html = await asyncio.to_thread(_fetch)

    ids: List[str] = []
    titles_by_id: Dict[str, str] = {}

    # Primary pattern — each result renderer has "videoId":"..." followed
    # shortly by its title. We pair them in one pass.
    pattern = re.compile(
        r'"videoId":"([a-zA-Z0-9_-]{11})".*?'
        r'"title":\{(?:"runs":\[\{"text":"([^"]+)"|"simpleText":"([^"]+)")',
        re.DOTALL,
    )
    for m in pattern.finditer(html):
        vid = m.group(1)
        title = m.group(2) or m.group(3) or ""
        if vid in titles_by_id:
            continue
        # Skip obvious non-watchable items (shorts / ads still use videoId but
        # we let them through — first watchable result is fine for 'play song').
        titles_by_id[vid] = title
        ids.append(vid)
        if len(ids) >= limit:
            break

    # Fallback — if the paired regex finds nothing (YouTube HTML change),
    # at least extract raw video IDs in order.
    if not ids:
        for vid in re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', html):
            if vid not in ids:
                ids.append(vid)
            if len(ids) >= limit:
                break

    titles = [titles_by_id.get(v, "") for v in ids]
    return ids, titles


@function_tool
async def search_youtube_video(query: str) -> str:
    """
    🎵 Searches YouTube and caches the top results for playback.

    Opens the results page in the default browser AND records the first
    10 video IDs in a module-level cache so `play_youtube_video(n)` can
    open the nth result directly via watch-URL (no vision clicks).

    Args:
        query: Video name, song, or channel

    Examples:
        - "Search YouTube for lofi music"
        - "Find Arijit Singh song"
    """
    try:
        encoded = urllib.parse.quote(query)
        search_url = f"https://www.youtube.com/results?search_query={encoded}"

        # Scrape first so the cache is populated before the browser opens.
        try:
            ids, titles = await _youtube_search_scrape(query, limit=10)
        except Exception as _e:
            logger.warning("YouTube scrape failed (falling back to search-page only): %s", _e)
            ids, titles = [], []

        _YT_LAST_SEARCH["query"] = query
        _YT_LAST_SEARCH["ids"] = ids
        _YT_LAST_SEARCH["titles"] = titles

        webbrowser.open(search_url)
        analytics.log_action("youtube_search", search_url,
                             {"query": query, "results": len(ids)})

        if ids:
            preview = titles[0] if titles and titles[0] else ids[0]
            return (
                f"✅ YouTube par '{query}' search kiya — {len(ids)} videos mil gaye. "
                f"Pehla: {preview[:70]}. 'play first' bolo to chala doongi."
            )
        return (
            f"⚠️ YouTube par '{query}' search kar diya but result parse nahi "
            f"ho paye. Browser mein tab khul gaya hai, manually click kar sakte ho."
        )

    except Exception as e:
        return f"❌ YouTube search fail: {str(e)}"


@function_tool
async def play_youtube_video(number: int = 1, query: str = "") -> str:
    """
    ▶️ Plays a YouTube video by search-result number.

    If ``query`` is given, a fresh search is performed first and the
    result is played in one call (handy for 'play Arijit song' style
    requests). Otherwise the most recent cached search is used.

    Directly opens ``https://www.youtube.com/watch?v=<id>`` in the
    default browser — no vision/clicks, no focus-window hacks, works at
    any screen resolution.

    Args:
        number: 1-based index into the search results (default 1 = top)
        query:  Optional — run a fresh search for this query first.

    Examples:
        - "Play first video"
        - "Play Arijit Singh romantic song on YouTube"
    """
    try:
        if query:
            try:
                ids, titles = await _youtube_search_scrape(query, limit=10)
            except Exception as _e:
                encoded = urllib.parse.quote(query)
                search_url = f"https://www.youtube.com/results?search_query={encoded}"
                webbrowser.open(search_url)
                analytics.log_action(
                    "youtube_search_fallback",
                    search_url,
                    {"query": query, "error": str(_e)[:180]},
                )
                return (
                    f"⚠️ YouTube result auto-play nahi ho paya, par '{query}' "
                    f"ka search page khol diya hai. Detail: {str(_e)}"
                )
            _YT_LAST_SEARCH["query"] = query
            _YT_LAST_SEARCH["ids"] = ids
            _YT_LAST_SEARCH["titles"] = titles

        ids: List[str] = _YT_LAST_SEARCH.get("ids") or []
        titles: List[str] = _YT_LAST_SEARCH.get("titles") or []
        last_q: str = _YT_LAST_SEARCH.get("query") or ""

        if not ids:
            return (
                "❌ Koi recent YouTube search nahi hai. "
                "Pehle 'search YouTube for <query>' bolo ya "
                "query argument ke saath bulao."
            )

        idx = max(1, int(number)) - 1
        if idx >= len(ids):
            return (
                f"❌ Sirf {len(ids)} results cached hain, "
                f"{number} number nahi mila."
            )

        vid_id = ids[idx]
        title = titles[idx] if idx < len(titles) and titles[idx] else vid_id
        watch_url = f"https://www.youtube.com/watch?v={vid_id}"
        webbrowser.open(watch_url)
        analytics.log_action(
            "play_youtube",
            watch_url,
            {"query": last_q, "number": number, "title": title[:120]},
        )
        return f"✅ Play kar rahi hoon: {title[:80]}  ({watch_url})"

    except Exception as e:
        return f"❌ Error: {str(e)}"


@function_tool
async def go_back() -> str:
    """
    ⬅️ Goes back in browser history.
    
    Examples:
        - "Go back"
        - "Previous page"
    """
    try:
        if controller.driver:
            controller.driver.back()
        else:
            pyautogui.hotkey('alt', 'left')
        
        analytics.log_action("go_back", "")
        return "✅ Peeche chali gayi hoon Sir!"
        
    except Exception as e:
        return f"❌ Go back fail: {str(e)}"


@function_tool
async def reload_browser_page() -> str:
    """
    🔄 Reloads current page.
    
    Examples:
        - "Reload page"
        - "Refresh browser"
    """
    try:
        if controller.driver:
            controller.driver.refresh()
        else:
            pyautogui.press('f5')
        
        analytics.log_action("reload", "")
        return "✅ Page reload kar diya!"
        
    except Exception as e:
        return f"❌ Reload fail: {str(e)}"


@function_tool
async def get_active_tab_url() -> str:
    """
    📋 Gets current tab URL.
    
    Examples:
        - "What's the current URL?"
        - "Get page address"
    """
    try:
        if controller.driver:
            url = controller.driver.current_url
            return url
        
        if PYPERCLIP_AVAILABLE:
            pyautogui.hotkey('ctrl', 'l')
            await asyncio.sleep(0.3)
            pyautogui.hotkey('ctrl', 'c')
            await asyncio.sleep(0.3)
            
            url = pyperclip.paste().strip()
            if url.startswith("http"):
                return url
        
        return "❌ URL detect nahi hui."
        
    except Exception as e:
        return f"❌ Error: {str(e)}"


@function_tool
async def smart_scroll_browser(direction: str = "down", amount: str = "medium") -> str:
    """
    📜 Smart scrolls browser page.
    
    Args:
        direction: 'up' or 'down'
        amount: 'small', 'medium', 'large'
    
    Examples:
        - "Scroll down"
        - "Scroll up a lot"
    """
    try:
        keys = {
            "down": {"small": "down", "medium": "pgdn", "large": "end"},
            "up": {"small": "up", "medium": "pgup", "large": "home"}
        }
        
        key = keys.get(direction, {}).get(amount, "pgdn")
        pyautogui.press(key)
        
        analytics.log_action("scroll", "", {"direction": direction, "amount": amount})
        
        return f"✅ Scrolled {direction} ({amount})."
        
    except Exception as e:
        return f"❌ Scroll fail: {str(e)}"


@function_tool
async def consult_web_ai(query: str, platform: str = "auto") -> str:
    """
    🤔 Consults Web AI (ChatGPT, Gemini, Claude, etc.).
    
    Args:
        query: Question to ask
        platform: 'auto', 'chatgpt', 'gemini', 'claude', 'perplexity'
    
    Examples:
        - "Ask ChatGPT about Python"
        - "Consult AI: What is quantum computing?"
    """
    try:
        platforms = Config.AI_PLATFORMS
        
        if platform == "auto" or platform not in platforms:
            platform = "chatgpt"
        
        url = platforms[platform]
        
        webbrowser.open(url)
        logger.info(f"🤖 Opening {platform}")
        
        await asyncio.sleep(4.0)
        
        # Type query
        if PYAUTOGUI_AVAILABLE:
            pyautogui.write(query, interval=0.01)
            await asyncio.sleep(0.5)
            pyautogui.press('enter')
        
        # Wait for response
        wait_time = min(5.0 + len(query) * 0.05, 15.0)
        await asyncio.sleep(wait_time)
        
        analytics.log_action("consult_ai", url, {"platform": platform, "query": query[:50]})
        
        return f"🤖 **{platform.title()}** se answer aa raha hai. Screen check karein!"
        
    except Exception as e:
        return f"❌ AI consult fail: {str(e)}"


@function_tool
async def take_browser_screenshot() -> str:
    """
    📸 Takes browser screenshot.
    
    Examples:
        - "Take screenshot"
        - "Capture current page"
    """
    try:
        if controller.driver:
            filepath = controller.take_screenshot()
            if filepath:
                return f"📸 Screenshot saved: `{filepath}`"
        
        # Fallback to pyautogui
        if PYAUTOGUI_AVAILABLE:
            home = os.path.expanduser("~")
            target_dir = os.path.join(home, Config.SCREENSHOT_DIR)
            Path(target_dir).mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = os.path.join(target_dir, f"shell_screen_{timestamp}.png")
            
            screenshot = pyautogui.screenshot()
            screenshot.save(filepath)
            
            return f"📸 Screenshot saved: `{filepath}`"
        
        return "❌ Screenshot not available."
        
    except Exception as e:
        return f"❌ Error: {str(e)}"


@function_tool
async def get_browser_status() -> str:
    """
    📊 Returns browser status, analytics, and module availability.

    Examples:
        - "Browser status"
        - "Show browsing stats"
    """
    try:
        stats = analytics.get_stats()
        state = controller.get_state() if controller.driver else None

        output = "📊 **Browser Status**\n\n"

        if state:
            output += f"**Browser:** {state.browser_name}\n"
            output += f"**Current URL:** {state.current_url[:50]}...\n"
            output += f"**Title:** {state.title[:30]}...\n"
            output += f"**Tabs:** {state.tab_count}\n"
            output += f"**Cookies:** {state.cookies_count}\n\n"

        output += f"**Total Actions:** {stats.get('total_actions', 0)}\n"

        if stats.get('top_domains'):
            output += "\n**Top Domains:**\n"
            for domain, count in list(stats['top_domains'].items())[:5]:
                output += f"  - {domain}: {count}\n"

        # Module availability status
        output += "\n**Module Status:**\n"
        output += f"  - Selenium: {'✅ Available' if SELENIUM_AVAILABLE else '❌ Not installed'}\n"
        output += f"  - PyAutoGUI: {'✅ Available' if PYAUTOGUI_AVAILABLE else '❌ Not installed'}\n"
        output += f"  - PIL/Pillow: {'✅ Available' if PIL_AVAILABLE else '❌ Not installed'}\n"
        output += f"  - Pyperclip: {'✅ Available' if PYPERCLIP_AVAILABLE else '❌ Not installed'}\n"

        # Bookmarks count
        bookmarks_count = 0
        bookmarks_file = Path("shell_bookmarks.json")
        if bookmarks_file.exists():
            try:
                with open(bookmarks_file, 'r') as f:
                    bookmarks_count = len(json.load(f))
            except Exception as _e:
                logger.debug("ignored Exception: %s", _e)
        output += f"\n**Total Bookmarks:** {bookmarks_count}\n"

        return output

    except Exception as e:
        return f"❌ Error: {str(e)}"


@function_tool
async def clear_browser_history() -> str:
    """
    🗑️ Clears browsing history.
    
    Examples:
        - "Clear history"
        - "Delete browsing data"
    """
    try:
        analytics.clear_history()
        return "✅ Browsing history cleared!"
        
    except Exception as e:
        return f"❌ Error: {str(e)}"


@function_tool
async def search_browser_history(query: str) -> str:
    """
    🔍 Searches browsing history.
    
    Args:
        query: Search term
    
    Examples:
        - "Find youtube in history"
        - "Search for github"
    """
    try:
        results = analytics.search_history(query)
        
        if not results:
            return "❌ History mein kuch nahi mila."
        
        output = f"📊 **Found {len(results)} results:**\n\n"
        
        for entry in results[:10]:
            output += f"- {entry.get('action', 'unknown')}: {entry.get('url', 'N/A')[:60]}\n"
        
        return output
        
    except Exception as e:
        return f"❌ Error: {str(e)}"


@function_tool
async def open_social_media(platform: str) -> str:
    """
    📱 Opens social media platform.
    
    Args:
        platform: 'twitter', 'facebook', 'instagram', 'linkedin', 'reddit'
    
    Examples:
        - "Open Twitter"
        - "Go to Instagram"
    """
    try:
        platforms = Config.SOCIAL_PLATFORMS
        
        if platform.lower() not in platforms:
            return f"❌ Unknown platform. Valid: {', '.join(platforms.keys())}"
        
        url = platforms[platform.lower()]
        webbrowser.open(url)
        
        analytics.log_action("open_social", url, {"platform": platform})
        
        return f"✅ {platform.title()} open kar diya!"
        
    except Exception as e:
        return f"❌ Error: {str(e)}"


@function_tool
async def enable_reading_mode() -> str:
    """
    📖 Enables browser reading mode (Edge/Chrome).
    
    Examples:
        - "Enable reading mode"
        - "Distraction-free reading"
    """
    try:
        # Edge reading mode shortcut
        pyautogui.hotkey('ctrl', 'shift', 'r')
        
        analytics.log_action("reading_mode", "")
        
        return "✅ Reading mode enable karne ki koshish ki!"
        
    except Exception as e:
        return f"❌ Error: {str(e)}"


@function_tool
async def translate_page_to(language: str) -> str:
    """
    🌐 Translates current page to language.
    
    Args:
        language: Target language (e.g., 'english', 'hindi', 'spanish')
    
    Examples:
        - "Translate to Hindi"
        - "Translate page to Spanish"
    """
    try:
        # Chrome translate shortcut (via Google Translate)
        if controller.driver:
            # json.dumps escapes quotes/backslashes so a malicious
            # `language` value can't break out of the JS string literal.
            script = f"""
            var translate = document.querySelector('google-translate-element');
            if (translate) {{
                var select = translate.shadowRoot.querySelector('select');
                if (select) select.value = {json.dumps(language)};
            }}
            """
            controller.execute_script(script)
        
        return f"🌐 Page ko {language} mein translate karne ki koshish ki!"
        
    except Exception as e:
        return f"❌ Error: {str(e)}"


@function_tool
async def bookmark_current_page(title: str = "") -> str:
    """
    🔖 Bookmarks current page.
    
    Args:
        title: Bookmark title (optional)
    
    Examples:
        - "Bookmark this page"
        - "Save to bookmarks"
    """
    try:
        url = await get_active_tab_url()
        
        # Save to bookmarks file
        bookmarks_file = Path("shell_bookmarks.json")
        
        bookmarks = []
        if bookmarks_file.exists():
            try:
                with open(bookmarks_file, 'r') as f:
                    bookmarks = json.load(f)
            except Exception as _e:
                logger.debug("ignored Exception: %s", _e)
        bookmark = {
            "title": title or "Untitled",
            "url": url,
            "timestamp": datetime.now().isoformat()
        }
        
        bookmarks.append(bookmark)
        
        with open(bookmarks_file, 'w') as f:
            json.dump(bookmarks, f, indent=2)
        
        analytics.log_action("bookmark", url, {"title": title})
        
        return f"🔖 Bookmarked: {title or url[:40]}..."
        
    except Exception as e:
        return f"❌ Error: {str(e)}"


@function_tool
async def get_bookmarks() -> str:
    """
    📚 Lists all bookmarks.
    
    Examples:
        - "Show bookmarks"
        - "List saved pages"
    """
    try:
        bookmarks_file = Path("shell_bookmarks.json")
        
        if not bookmarks_file.exists():
            return "📚 Koi bookmarks nahi hain."
        
        with open(bookmarks_file, 'r') as f:
            bookmarks = json.load(f)
        
        output = f"📚 **Bookmarks ({len(bookmarks)}):**\n\n"
        
        for bm in bookmarks[-20:]:  # Last 20
            output += f"- **{bm.get('title', 'Untitled')}**\n  {bm.get('url', 'N/A')}\n\n"
        
        return output
        
    except Exception as e:
        return f"❌ Error: {str(e)}"


# =============================================================================
# 🆕 NEW TAB & PAGE MANAGEMENT TOOLS
# =============================================================================

@function_tool
async def open_new_tab_tool(url: str = "") -> str:
    """
    ➕ Opens a new browser tab. Optionally navigates to a URL.

    Args:
        url: Website URL to open in new tab (optional, opens blank tab if empty)

    Examples:
        - "Open new tab"
        - "New tab with google.com"
        - "Open new tab youtube"
    """
    try:
        if not PYAUTOGUI_AVAILABLE:
            return "❌ PyAutoGUI not installed. Install: pip install pyautogui"

        # Open new tab with Ctrl+T
        pyautogui.hotkey('ctrl', 't')
        await asyncio.sleep(0.8)

        if url and url.strip():
            # URL shortcuts support
            URL_SHORTCUTS = {
                "google": "https://www.google.com",
                "youtube": "https://www.youtube.com",
                "github": "https://www.github.com",
                "gmail": "https://mail.google.com",
            }
            url_lower = url.strip().lower()
            if url_lower in URL_SHORTCUTS:
                url = URL_SHORTCUTS[url_lower]

            # Validate URL
            valid, result = BrowserSecurityValidator.validate_url(url)
            if not valid:
                return result
            url = result

            # Type URL in address bar (new tab already focuses address bar)
            pyautogui.typewrite(url, interval=0.01)
            await asyncio.sleep(0.3)
            pyautogui.press('enter')

            analytics.log_action("open_new_tab", url)
            return f"✅ Naya tab open karke {url} par navigate kar diya Sir!"
        else:
            analytics.log_action("open_new_tab", "about:blank")
            return "✅ Naya blank tab open kar diya hai Sir!"

    except Exception as e:
        return f"❌ New tab open karne mein error: {str(e)}"


@function_tool
async def close_current_tab_tool() -> str:
    """
    ❌ Closes the current browser tab.

    Examples:
        - "Close this tab"
        - "Close current tab"
        - "Tab band karo"
    """
    try:
        if not PYAUTOGUI_AVAILABLE:
            return "❌ PyAutoGUI not installed. Install: pip install pyautogui"

        pyautogui.hotkey('ctrl', 'w')
        await asyncio.sleep(0.5)

        analytics.log_action("close_tab", "")
        return "✅ Current tab band kar diya hai Sir!"

    except Exception as e:
        return f"❌ Tab close karne mein error: {str(e)}"


@function_tool
async def switch_tab_tool(direction: str = "next") -> str:
    """
    🔄 Switches between browser tabs.

    Args:
        direction: 'next' (Ctrl+Tab), 'previous' (Ctrl+Shift+Tab), or a number 1-9 (Ctrl+number)

    Examples:
        - "Next tab"
        - "Previous tab"
        - "Switch to tab 3"
        - "Go to tab 1"
    """
    try:
        if not PYAUTOGUI_AVAILABLE:
            return "❌ PyAutoGUI not installed. Install: pip install pyautogui"

        direction = direction.strip().lower()

        if direction == "next":
            pyautogui.hotkey('ctrl', 'tab')
            msg = "✅ Next tab par switch kar diya Sir!"
        elif direction == "previous" or direction == "prev":
            pyautogui.hotkey('ctrl', 'shift', 'tab')
            msg = "✅ Previous tab par switch kar diya Sir!"
        elif direction.isdigit() and 1 <= int(direction) <= 9:
            pyautogui.hotkey('ctrl', direction)
            msg = f"✅ Tab {direction} par switch kar diya Sir!"
        else:
            return f"❌ Invalid direction: '{direction}'. Use 'next', 'previous', or a number 1-9."

        await asyncio.sleep(0.3)
        analytics.log_action("switch_tab", "", {"direction": direction})
        return msg

    except Exception as e:
        return f"❌ Tab switch karne mein error: {str(e)}"


@function_tool
async def zoom_page_tool(action: str = "in") -> str:
    """
    🔍 Zooms in, out, or resets zoom on the current page.

    Args:
        action: 'in' (Ctrl++), 'out' (Ctrl+-), 'reset' (Ctrl+0)

    Examples:
        - "Zoom in"
        - "Zoom out"
        - "Reset zoom"
        - "Page bada karo"
    """
    try:
        if not PYAUTOGUI_AVAILABLE:
            return "❌ PyAutoGUI not installed. Install: pip install pyautogui"

        action = action.strip().lower()

        if action == "in":
            pyautogui.hotkey('ctrl', 'plus')
            # Also try with '=' key since Ctrl+= is zoom in on most keyboards
            await asyncio.sleep(0.1)
            pyautogui.hotkey('ctrl', '=')
            msg = "✅ Page zoom in kar diya Sir! 🔍"
        elif action == "out":
            pyautogui.hotkey('ctrl', '-')
            msg = "✅ Page zoom out kar diya Sir! 🔍"
        elif action == "reset":
            pyautogui.hotkey('ctrl', '0')
            msg = "✅ Page zoom reset kar diya Sir! (100%) 🔍"
        else:
            return f"❌ Invalid action: '{action}'. Use 'in', 'out', or 'reset'."

        await asyncio.sleep(0.2)
        analytics.log_action("zoom_page", "", {"action": action})
        return msg

    except Exception as e:
        return f"❌ Zoom karne mein error: {str(e)}"


@function_tool
async def download_page_as_pdf_tool() -> str:
    """
    📄 Saves the current page as PDF using the browser's Print dialog.

    Uses Ctrl+P to open print dialog, then attempts to save as PDF.

    Examples:
        - "Save page as PDF"
        - "Download this page as PDF"
        - "Page PDF mein save karo"
    """
    try:
        if not PYAUTOGUI_AVAILABLE:
            return "❌ PyAutoGUI not installed. Install: pip install pyautogui"

        # Open print dialog with Ctrl+P
        pyautogui.hotkey('ctrl', 'p')
        await asyncio.sleep(2.0)

        # In Chrome/Edge, the print dialog opens. We try to select "Save as PDF"
        # The default destination might already be "Save as PDF" or we need to change it.
        # Press Enter to confirm (if Save as PDF is default) or handle the dialog.

        # Wait for print dialog to fully load
        await asyncio.sleep(1.5)

        # Press Enter to trigger save (works if "Save as PDF" is the default printer)
        pyautogui.press('enter')
        await asyncio.sleep(1.5)

        # If a file save dialog appears, press Enter to confirm default filename
        pyautogui.press('enter')
        await asyncio.sleep(1.0)

        analytics.log_action("download_pdf", "")
        return "✅ Page ko PDF mein save karne ki koshish ki hai Sir! Print dialog se 'Save as PDF' select karein agar automatically nahi hua."

    except Exception as e:
        return f"❌ PDF save karne mein error: {str(e)}"


# =============================================================================
# 🧪 TEST MODE
# =============================================================================

if __name__ == "__main__":
    if sys.platform == 'win32':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception as _e:
            logger.debug("ignored Exception: %s", _e)
    logger.info("[SHELL_BROWSER_CTRL_MEGA] Test Mode")
    logger.info("=" * 60)

    async def test_browser_features():
        # Test 1: Open URL
        logger.info("[TEST 1] Open URL...")
        result = await open_browser_url("google.com")
        logger.info(result)

        # Test 2: Google search
        logger.info("[TEST 2] Google search...")
        result = await search_google("Python programming")
        logger.info(result)

        # Test 3: Status
        logger.info("[TEST 3] Browser status...")
        result = await get_browser_status()
        logger.info(result)

        # Test 4: Screenshot
        logger.info("[TEST 4] Screenshot...")
        result = await take_browser_screenshot()
        logger.info(result)

        logger.info("[TEST] All tests completed!")
    
    asyncio.run(test_browser_features())
