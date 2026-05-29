from __future__ import annotations

import cv2
import numpy as np
import pyautogui
import time
import logging
import pytesseract
from PIL import Image, ImageDraw, ImageFont
from typing import Optional, Tuple, Dict, Any, List
import asyncio
import os
from dotenv import load_dotenv

# Initialize Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("shell_vision")

# Force Load Env
load_dotenv()

# --- 1. ROBUST TESSERACT SETUP ---
import shutil
TESSERACT_AVAILABLE = False
def find_tesseract():
    global TESSERACT_AVAILABLE

    local = os.environ.get('LOCALAPPDATA', '')
    program_files = os.environ.get('ProgramFiles', r'C:\Program Files')
    program_files_x86 = os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')
    user_profile = os.environ.get('USERPROFILE', '')

    # Priority order:
    # 1. explicit override from .env (TESSERACT_CMD)
    # 2. 'tesseract' on PATH (resolved via shutil.which)
    # 3. common Windows install locations (installer, winget, scoop, chocolatey)
    # 4. common Linux/macOS paths
    # 5. fallback 'tesseract' — let pytesseract try PATH directly
    paths: list[str] = []

    env_override = os.environ.get('TESSERACT_CMD', '').strip().strip('"').strip("'")
    if env_override:
        paths.append(env_override)

    which = shutil.which('tesseract')
    if which:
        paths.append(which)

    paths.extend([
        os.path.join(program_files, 'Tesseract-OCR', 'tesseract.exe'),
        os.path.join(program_files_x86, 'Tesseract-OCR', 'tesseract.exe'),
        os.path.join(local, 'Programs', 'Tesseract-OCR', 'tesseract.exe'),
        os.path.join(local, 'Tesseract-OCR', 'tesseract.exe'),
        os.path.join(local, 'Microsoft', 'WinGet', 'Links', 'tesseract.exe'),
        os.path.join(user_profile, 'scoop', 'shims', 'tesseract.exe'),
        r'C:\ProgramData\chocolatey\bin\tesseract.exe',
        '/usr/local/bin/tesseract',
        '/usr/bin/tesseract',
        '/opt/homebrew/bin/tesseract',
        'tesseract',
    ])

    # Dedup while preserving order, drop empties.
    seen = set()
    ordered: list[str] = []
    for p in paths:
        if not p or p in seen:
            continue
        seen.add(p)
        ordered.append(p)

    for p in ordered:
        try:
            pytesseract.pytesseract.tesseract_cmd = p
            version = pytesseract.get_tesseract_version()
            logger.info("✅ Tesseract %s found at: %s", version, p)
            TESSERACT_AVAILABLE = True
            return
        except Exception:
            continue

    logger.warning(
        "⚠️ Tesseract not found — OCR will fall back to Gemini Vision (slower). "
        "To install on Windows run: winget install UB-Mannheim.TesseractOCR "
        "or set TESSERACT_CMD in .env. Paths tried: %d.",
        len(ordered),
    )
    TESSERACT_AVAILABLE = False

find_tesseract()

# --- 2. GEMINI SETUP (dual-SDK — prefer google-genai, fall back to legacy) ---
# The legacy `google.generativeai` package is deprecated. We try the new
# `google.genai` Client API first and fall back to legacy only if it's
# not installed. Both paths end up setting VisionEngine.gemini_ready.
_NEW_GENAI_AVAILABLE = False
_LEGACY_GENAI_AVAILABLE = False
try:
    from google import genai as _new_genai_mod
    _NEW_GENAI_AVAILABLE = True
except ImportError:
    _new_genai_mod = None  # type: ignore[assignment]
_legacy_genai_mod = None  # type: ignore[assignment]


def _load_legacy_genai() -> bool:
    """Load deprecated google-generativeai only as an optional fallback."""
    global _LEGACY_GENAI_AVAILABLE, _legacy_genai_mod, genai, GENAI_PKG_AVAILABLE
    if _LEGACY_GENAI_AVAILABLE:
        return True
    try:
        import google.generativeai as legacy_genai_mod
    except ImportError:
        _legacy_genai_mod = None  # type: ignore[assignment]
        return False
    _legacy_genai_mod = legacy_genai_mod
    _LEGACY_GENAI_AVAILABLE = True
    genai = _new_genai_mod or _legacy_genai_mod
    GENAI_PKG_AVAILABLE = True
    return True


if not _NEW_GENAI_AVAILABLE:
    _load_legacy_genai()

# Back-compat alias for any external code that still imports `genai` from
# this module (historical users did `from vision_engine import genai`).
genai = _new_genai_mod or _legacy_genai_mod
GENAI_PKG_AVAILABLE = _NEW_GENAI_AVAILABLE or _LEGACY_GENAI_AVAILABLE


# --- 3. VISION ENGINE CLASS ---
class VisionEngine:
    def __init__(self, confidence=0.8):
        self.confidence = confidence
        self.gemini_ready = False
        self._client_mode: str | None = None   # "new" | "legacy" | None
        self._new_client = None                # google.genai.Client instance
        self._setup_gemini()

    def _setup_gemini(self):
        key = os.getenv("GOOGLE_API_KEY")
        if not key:
            return

        # Prefer the new SDK — it's the supported path going forward.
        if _NEW_GENAI_AVAILABLE:
            try:
                self._new_client = _new_genai_mod.Client(api_key=key)
                self._client_mode = "new"
                self.gemini_ready = True
                logger.info("✅ Gemini Vision Client Ready (google-genai, new SDK).")
                return
            except Exception as e:
                logger.debug("google-genai Client init failed, trying legacy: %s", e)

        if not _LEGACY_GENAI_AVAILABLE:
            _load_legacy_genai()

        if _LEGACY_GENAI_AVAILABLE:
            try:
                _legacy_genai_mod.configure(api_key=key)
                self._client_mode = "legacy"
                self.gemini_ready = True
                logger.info("✅ Gemini Vision Client Ready (google-generativeai, legacy SDK).")
                return
            except Exception as e:
                logger.error(f"❌ Legacy Gemini init failed: {e}")

        if not self.gemini_ready:
            logger.warning(
                "⚠️ No Gemini SDK available. pip install google-genai (preferred) "
                "or google-generativeai."
            )

    def _gemini_generate(self, model_name: str, contents):
        """Route generate_content through whichever SDK is live."""
        if self._client_mode == "new":
            return self._new_client.models.generate_content(
                model=model_name, contents=contents,
            )
        if self._client_mode == "legacy":
            model = _legacy_genai_mod.GenerativeModel(model_name=model_name)
            return model.generate_content(contents)
        raise RuntimeError("Gemini not initialised; call _setup_gemini first.")

    def verify_vision_system(self) -> bool:
        """Verifies if the vision system is operational (Either Gemini or Tesseract)"""
        if self.gemini_ready:
            return True
        if TESSERACT_AVAILABLE:
            return True
        return False

    def capture_screen(self, region=None) -> Image.Image:
        """Captures screen safely."""
        return pyautogui.screenshot(region=region)

    def analyze_with_gemini(self, image: Image.Image, prompt: str, timeout: int = 30) -> str:
        """
        Multimodal Fallback Analysis with timeout protection.
        Chain: gemini-2.5-flash -> gemini-2.0-flash -> gemini-2.0-flash-lite -> gemini-1.5-flash

        Args:
            image: PIL Image to analyze
            prompt: Analysis prompt
            timeout: Max seconds per model attempt (default 30)
        """
        if not self.gemini_ready:
            return "[FAIL] Gemini Not Initialized"

        models = [
            'gemini-2.5-flash',
            'gemini-2.0-flash',
            'gemini-2.0-flash-lite',
            'gemini-1.5-flash',
        ]

        errors = []
        for model_name in models:
            try:
                # Run through the SDK-agnostic helper + enforce a timeout so a
                # stuck network call cannot freeze the caller's event loop.
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(self._gemini_generate, model_name, [prompt, image])
                    response = future.result(timeout=timeout)
                if response.text:
                    return response.text.strip()
            except concurrent.futures.TimeoutError:
                errors.append(f"{model_name}: Timeout ({timeout}s)")
                logger.warning(f"Gemini model {model_name} timed out after {timeout}s")
                continue
            except Exception as e:
                errors.append(f"{model_name}: {e}")
                continue

        return f"[FAIL] All Models Failed: {errors}"

    def read_screen_text(self, region=None) -> str:
        """Hybrid read: local OCR first, Gemini fallback when configured."""
        screenshot = self.capture_screen(region)
        
        # Method A: Hyper-Optimized Local OCR (Primary)
        if TESSERACT_AVAILABLE:
            try:
                img = np.array(screenshot)
                img = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
                # OCR pre-processing: contrast enhancement + Otsu threshold.
                img = cv2.convertScaleAbs(img, alpha=1.5, beta=0) 
                img = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
                
                # Assume standard english text layout
                custom_config = r'--oem 3 --psm 11' 
                ocr_text = pytesseract.image_to_string(img, config=custom_config).strip()
                if len(ocr_text) > 5:
                    return ocr_text
            except Exception as e:
                logger.warning(f"OCR Error: {e}, falling back to Cloud Vision")
        
        # Method B: Cloud Vision (Fallback)
        if self.gemini_ready:
            res = self.analyze_with_gemini(screenshot, "Extract all visible text from this interface exactly as it appears. Output ONLY the text.")
            if "[FAIL]" not in res:
                return res
        
        return "❌ Vision Unavailable (No API + No Tesseract)"

    def vision_click(self, target: str) -> Optional[Tuple[int, int]]:
        """
        Vision targeting:
        1. OCR centroid calculation.
        2. Gemini Fallback for graphical icons entirely lacking text.
        """
        screenshot = self.capture_screen()
        
        # Phase 1: High-Speed OCR Targeting
        if TESSERACT_AVAILABLE:
            try:
                data = pytesseract.image_to_data(screenshot, output_type=pytesseract.Output.DICT)
                target_lower = target.lower()
                n_boxes = len(data['text'])
                
                # Check for exact matches first
                for i in range(n_boxes):
                    if data['text'][i].lower() == target_lower:
                        x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
                        return (x + w//2, y + h//2)
                
                # Fallback to partial matches
                for i in range(n_boxes):
                    if target_lower in data['text'][i].lower() and len(data['text'][i].strip()) > 2:
                        x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
                        return (x + w//2, y + h//2)
            except Exception as e:
                logger.warning(f"OCR Targeting Error: {e}")
                
        # Phase 2: Multimodal Icon Mapping (Experimental Fallback)
        if self.gemini_ready:
            try:
                # Ask Gemini to describe where it is broadly (Top-left, center, etc.)
                # In a true Prod environment, you'd draw a coordinate grid on the image payload.
                res = self.analyze_with_gemini(screenshot, f"Locate the '{target}' button/icon. Reply ONLY with its approximate X, Y pixel coordinates on a 1920x1080 screen formatted as X,Y. If not found reply NOT_FOUND.")
                if "NOT_FOUND" not in res and "," in res:
                    parts = res.split(",")
                    try:
                        x = int(parts[0].strip())
                        y = int(parts[-1].strip())
                        if 0 <= x <= 3840 and 0 <= y <= 2160:
                            return (x, y)
                        else:
                            logger.warning(f"Gemini returned out-of-bounds coordinates: ({x}, {y})")
                    except (ValueError, IndexError) as e:
                        logger.warning(f"Gemini coordinate parse error: {e}, raw='{res}'")
            except Exception as e:
                 logger.warning(f"Gemini Targeting Error: {e}")

        return None
    
    def find_multiple_markers(self, markers: List[str]) -> Dict[str, List[Tuple[int, int]]]:
        """Find multiple text markers on screen and return their coordinates"""
        results = {m: [] for m in markers}
        
        if TESSERACT_AVAILABLE:
            try:
                screenshot = self.capture_screen()
                data = pytesseract.image_to_data(screenshot, output_type=pytesseract.Output.DICT)
                n_boxes = len(data['text'])
                
                # Check each text box against all markers
                for i in range(n_boxes):
                    text = data['text'][i].lower()
                    if not text.strip(): continue
                    
                    for marker in markers:
                        if marker.lower() in text:
                            x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
                            center = (x + w//2, y + h//2)
                            results[marker].append(center)
                            # Dont break here, one text box usually matches one marker, but technically could be multiple
            except Exception as e:
                logger.error(f"Error finding markers: {e}")
        
        return results

# Singleton
vision_engine = VisionEngine()

# --- 4. LIVEKIT TOOLS (LAZY IMPORT TO PREVENT CIRCULAR DEP OR BLOCKING) ---
# Only define these if running inside the agent process
try:
    from shell_safe_executor import god_tier_tool as function_tool
    
    @function_tool
    async def read_screen_text_tool() -> str:
        text = await asyncio.to_thread(vision_engine.read_screen_text)
        return text if text else "Screen Empty"

    @function_tool
    async def extract_text_from_image() -> str:
        """Reads text from the current screen (Alias for consistency)."""
        return await read_screen_text_tool()

    @function_tool
    async def describe_screen_tool(prompt: str = "Describe what is on the screen in detail.") -> str:
        """
        Uses Vision AI to describe the screen content.
        Args:
            prompt: What to analyze (e.g., 'what app is open?', 'describe the error message').
        """
        screen = await asyncio.to_thread(vision_engine.capture_screen)
        desc = await asyncio.to_thread(vision_engine.analyze_with_gemini, screen, prompt)
        return desc

    @function_tool
    async def analyze_ui_state_tool() -> str:
        """
        SEMANTIC UI UNDERSTANDING.
        Tells the AI *what* the user is doing — active windows, buttons, state.
        Returns a structured JSON description.
        """
        prompt = (
            "Analyze this screenshot and return a JSON object describing the UI state. "
            "Include: 'active_window' (name), 'context' (what is the user doing?), "
            "'clickable_elements' (list of visible buttons/links), "
            "'notifications' (any popups/alerts visible), "
            "'text_content' (key text visible on screen). "
            "Output ONLY valid JSON."
        )
        screen = await asyncio.to_thread(vision_engine.capture_screen)
        desc = await asyncio.to_thread(vision_engine.analyze_with_gemini, screen, prompt)
        return desc

    @function_tool
    async def click_on_screen_element(target: str) -> str:
        """
        Uses Omni-Sight to find and click an element on the screen.
        Args:
            target: Text label or description of element to click (e.g., 'OK button', 'Close', 'Settings').
        """
        coords = await asyncio.to_thread(vision_engine.vision_click, target)
        if coords:
            try:
                from keyboard_mouse_CTRL import move_cursor_to_position_tool, mouse_click_tool
                await move_cursor_to_position_tool(coords[0], coords[1])
                await mouse_click_tool("left")
                return f"🎯 Omni-Sight clicked: '{target}' at {coords}"
            except ImportError:
                pyautogui.click(coords[0], coords[1])
                return f"🎯 Clicked '{target}' at {coords}"
        return f"❌ Could not locate '{target}' on the screen."

    @function_tool
    async def find_text_on_screen_tool(text: str) -> str:
        """
        Searches for specific text on the screen and returns its location.
        Args:
            text: Text to find (e.g., 'Save', 'Error', 'OK').
        """
        try:
            screenshot = await asyncio.to_thread(vision_engine.capture_screen)
            if TESSERACT_AVAILABLE:
                data = await asyncio.to_thread(
                    pytesseract.image_to_data, screenshot,
                    output_type=pytesseract.Output.DICT
                )
                matches = []
                n_boxes = len(data['text'])
                text_lower = text.lower()
                for i in range(n_boxes):
                    if text_lower in data['text'][i].lower() and data['text'][i].strip():
                        x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
                        matches.append(f"  - '{data['text'][i]}' at ({x+w//2}, {y+h//2})")
                if matches:
                    return f"🔍 Found '{text}' at:\n" + "\n".join(matches)
                return f"❌ '{text}' not found on screen."
            else:
                # Gemini fallback
                res = await asyncio.to_thread(
                    vision_engine.analyze_with_gemini, screenshot,
                    f"Is the text '{text}' visible on this screen? If yes, describe where it is. If no, say NOT_FOUND."
                )
                return res
        except Exception as e:
            return f"❌ Text search error: {e}"

    @function_tool
    async def get_screen_colors_tool() -> str:
        """Analyzes dominant colors visible on screen — useful for detecting themes, errors (red), etc."""
        try:
            screenshot = await asyncio.to_thread(vision_engine.capture_screen)
            img = np.array(screenshot)
            # Sample center region
            h, w = img.shape[:2]
            center = img[h//4:3*h//4, w//4:3*w//4]
            avg_color = center.mean(axis=(0, 1)).astype(int)

            # Detect dominant colors
            from collections import Counter
            pixels = center.reshape(-1, 3)
            # Quantize to reduce colors
            quantized = (pixels // 32) * 32
            color_counts = Counter([tuple(c) for c in quantized])
            top_colors = color_counts.most_common(5)

            def rgb_name(r, g, b):
                if r > 200 and g < 80 and b < 80: return "Red"
                if r < 80 and g > 200 and b < 80: return "Green"
                if r < 80 and g < 80 and b > 200: return "Blue"
                if r > 200 and g > 200 and b < 80: return "Yellow"
                if r > 200 and g > 200 and b > 200: return "White"
                if r < 60 and g < 60 and b < 60: return "Black"
                if r > 150 and g > 150 and b > 150: return "Light Gray"
                if r < 100 and g < 100 and b < 100: return "Dark Gray"
                return f"RGB({r},{g},{b})"

            colors_str = "\n".join(
                f"  - {rgb_name(*c[0])}: {c[1]} pixels"
                for c in top_colors
            )

            is_dark = avg_color.mean() < 100
            theme = "Dark Theme" if is_dark else "Light Theme"

            return f"🎨 Screen Color Analysis:\n  Theme: {theme}\n  Top colors:\n{colors_str}"
        except Exception as e:
            return f"❌ Color analysis error: {e}"

except ImportError:
    pass
