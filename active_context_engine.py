import ctypes
import time
import os
import datetime
import logging
from shell_safe_executor import god_tier_tool as function_tool

logger = logging.getLogger("active_context_engine")

try:
    import win32com.client
    import win32gui
    import win32api
    import win32con
    import win32clipboard
    import win32process
    WINDOWS_CONTEXT_AVAILABLE = True
except Exception as _win_import_error:
    win32com = None
    win32gui = None
    win32api = None
    win32con = None
    win32clipboard = None
    win32process = None
    WINDOWS_CONTEXT_AVAILABLE = False
    logger.info("Windows active-context APIs unavailable on this platform: %s", _win_import_error)

# File extension to type category mapping
_FILE_TYPE_MAP = {
    # Image
    '.png': 'Image', '.jpg': 'Image', '.jpeg': 'Image', '.gif': 'Image',
    '.bmp': 'Image', '.ico': 'Image', '.svg': 'Image', '.webp': 'Image', '.tiff': 'Image',
    # Video
    '.mp4': 'Video', '.avi': 'Video', '.mkv': 'Video', '.mov': 'Video',
    '.wmv': 'Video', '.flv': 'Video', '.webm': 'Video',
    # Audio
    '.mp3': 'Audio', '.wav': 'Audio', '.flac': 'Audio', '.aac': 'Audio',
    '.ogg': 'Audio', '.wma': 'Audio',
    # Code
    '.py': 'Code', '.js': 'Code', '.ts': 'Code', '.java': 'Code', '.cpp': 'Code',
    '.c': 'Code', '.h': 'Code', '.cs': 'Code', '.go': 'Code', '.rs': 'Code',
    '.rb': 'Code', '.php': 'Code', '.swift': 'Code', '.kt': 'Code',
    '.html': 'Code', '.css': 'Code', '.jsx': 'Code', '.tsx': 'Code',
    # Document
    '.pdf': 'Document', '.doc': 'Document', '.docx': 'Document',
    '.xls': 'Document', '.xlsx': 'Document', '.ppt': 'Document', '.pptx': 'Document',
    '.txt': 'Document', '.md': 'Document', '.rtf': 'Document', '.odt': 'Document',
    # Data
    '.json': 'Data', '.xml': 'Data', '.csv': 'Data', '.yaml': 'Data', '.yml': 'Data',
    '.sql': 'Data', '.db': 'Data', '.sqlite': 'Data',
    # Archive
    '.zip': 'Archive', '.rar': 'Archive', '.7z': 'Archive', '.tar': 'Archive',
    '.gz': 'Archive',
    # Executable
    '.exe': 'Executable', '.msi': 'Executable', '.bat': 'Executable',
    '.cmd': 'Executable', '.ps1': 'Executable', '.sh': 'Executable',
}


def _get_file_type_category(ext: str) -> str:
    """Returns the category for a file extension."""
    return _FILE_TYPE_MAP.get(ext.lower(), 'Other')


def _get_image_dimensions(filepath: str) -> str:
    """Tries to get image dimensions using PIL. Returns dimensions string or empty."""
    try:
        from PIL import Image
        with Image.open(filepath) as img:
            w, h = img.size
            return f"{w}x{h}px"
    except Exception:
        return ""

def get_files_from_clipboard_fallback():
    """
    Simulates Ctrl+C and reads file paths from clipboard (CF_HDROP).
    Use as fallback when COM fails (e.g. Desktop).
    """
    try:
        if not WINDOWS_CONTEXT_AVAILABLE:
            return []
        # 1. Clear clipboard to ensure we don't read old data
        try:
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.CloseClipboard()
        except Exception:
            pass  # Clipboard may be locked by another process

        # 2. Press Ctrl+C
        win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
        win32api.keybd_event(0x43, 0, 0, 0) # C key
        time.sleep(0.05)
        win32api.keybd_event(0x43, 0, win32con.KEYEVENTF_KEYUP, 0)
        win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
        
        # Wait for clipboard update
        time.sleep(0.2)
        
        # 3. Read CF_HDROP
        files = []
        try:
            win32clipboard.OpenClipboard()
            if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_HDROP):
                files = win32clipboard.GetClipboardData(win32clipboard.CF_HDROP)
        finally:
            try:
                win32clipboard.CloseClipboard()
            except Exception as _e:
                logger.debug("ignored Exception: %s", _e)

        return list(files) if files else []
        
    except Exception as e:
        logger.error(f"Clipboard Context Fallback Error: {e}")
        return []

@function_tool
async def get_selected_file_context_tool() -> str:
    """
    Intelligently inspects the file(s) currently selected by the user in Windows Explorer.
    Returns: File Path, Size, Type, and a CONTENT PREVIEW (if text/code).
    Use this when user says "Is file ko padho", "Ye kya hai", or "Check this".
    """
    try:
        if not WINDOWS_CONTEXT_AVAILABLE:
            return "Selected-file context is Windows Explorer only. On this platform, use workspace/file tools instead."
        selection_list = []
        
        # --- METHOD 1: COM (Shell.Application) ---
        try:
            shell = win32com.client.Dispatch("Shell.Application")
            fg_window = win32gui.GetForegroundWindow()
            
            for window in shell.Windows():
                try:
                    # Loose matching for focused window
                    if window.hwnd == fg_window:
                        items = window.Document.SelectedItems()
                        for item in items: selection_list.append(item.Path)
                except (AttributeError, Exception):
                    pass  # Window may not have Document/SelectedItems
                
            # If nothing found, try all windows (catch-all)
            if not selection_list:
                for window in shell.Windows():
                    try:
                        items = window.Document.SelectedItems()
                        for item in items: selection_list.append(item.Path)
                    except (AttributeError, Exception):
                        pass  # Window may not support selection
        except Exception as e:
            logger.warning(f"COM Method failed: {e}")

        selection_list = list(set(selection_list))

        # --- METHOD 2: CLIPBOARD FALLBACK (For Desktop/Tricky Windows) ---
        if not selection_list:
            logger.info("⚠️ No selection via COM. Attempting Clipboard Fallback...")
            selection_list = get_files_from_clipboard_fallback()

        # --- PROCESS RESULT ---
        # --- PROCESS RESULT ---
        if not selection_list:
            return "❌ No file selected. Please select a file and try again."

        count = len(selection_list)
        context = f"📂 **Selected Files ({count})**:\n"
        
        # List all files (up to 20 to avoid token overflow)
        for i, path in enumerate(selection_list[:20]):
            context += f"{i+1}. `{path}`\n"
            
        if count > 20:
            context += f"... and {count - 20} more files.\n"

        # Preview first file if it's text/code (as a sample)
        first_file = selection_list[0]
        if os.path.exists(first_file):
            stat = os.stat(first_file)
            size_mb = stat.st_size / (1024 * 1024)
            context += f"\n📊 **First File Size**: {size_mb:.2f} MB"

            ext = os.path.splitext(first_file)[1].lower()
            file_category = _get_file_type_category(ext)
            context += f"\n🏷️ **Extension**: {ext if ext else 'N/A'} | **Type**: {file_category}"

            # Created and Modified dates
            created_time = datetime.datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
            modified_time = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            context += f"\n📅 **Created**: {created_time} | **Modified**: {modified_time}"

            # Image dimensions if applicable
            if file_category == "Image":
                dims = _get_image_dimensions(first_file)
                if dims:
                    context += f"\n🖼️ **Dimensions**: {dims}"
                else:
                    context += f"\n🖼️ **Dimensions**: Pata nahi chal paya (PIL not available ya corrupt file)"

            text_exts = ['.txt', '.py', '.js', '.md', '.json', '.html', '.css', '.bat', '.log', '.ini', '.xml', '.csv']

            if ext in text_exts:
                try:
                    with open(first_file, "r", encoding="utf-8", errors="ignore") as f:
                         preview = f.read(500) # Read first 500 chars
                         context += f"\n📜 **Preview ({os.path.basename(first_file)})**:\n```\n{preview}\n...```"
                except Exception as read_err:
                     context += f"\n⚠️ Read Error: {read_err}"
            else:
                 context += "\n📝 (First file is Binary/Media - Content not previewed)"

        return context

    except Exception as e:
        logger.error(f"Context Error: {e}")
        return f"❌ Error retrieving context: {str(e)}"


@function_tool
async def get_clipboard_text_tool() -> str:
    """
    📋 Clipboard se current text content read karta hai (CF_TEXT / CF_UNICODETEXT).
    Reads current text from clipboard. Useful jab user kuch copy kare aur Shell se process karwaye.
    Use when user says 'clipboard padho', 'jo copy kiya hai wo dekho', 'paste karke batao'.
    """
    try:
        if not WINDOWS_CONTEXT_AVAILABLE:
            try:
                import pyperclip
                text = str(pyperclip.paste() or "").strip()
                if text:
                    preview = text[:2000]
                    suffix = f"\n\n[TRUNCATED — {len(text) - 2000} aur characters hain]" if len(text) > 2000 else ""
                    return f"📋 **Clipboard Text**\n{'─' * 40}\n📏 Length: {len(text)} chars | {text.count(chr(10)) + 1} lines\n{'─' * 40}\n{preview}{suffix}"
            except Exception as clip_err:
                logger.debug("cross-platform clipboard fallback failed: %s", clip_err)
            return "📋 Clipboard text unavailable on this platform."
        win32clipboard.OpenClipboard()
        try:
            # Try Unicode first
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                data = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
                if data:
                    text = str(data).strip()
                    if not text:
                        return "📋 Clipboard mein text hai lekin khali hai (empty string)."
                    char_count = len(text)
                    line_count = text.count('\n') + 1
                    preview = text[:2000]
                    result = f"📋 **Clipboard Text**\n{'─' * 40}\n"
                    result += f"📏 Length: {char_count} chars | {line_count} lines\n"
                    result += f"{'─' * 40}\n{preview}"
                    if char_count > 2000:
                        result += f"\n\n[TRUNCATED — {char_count - 2000} aur characters hain]"
                    return result

            # Fallback to CF_TEXT (ANSI)
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_TEXT):
                data = win32clipboard.GetClipboardData(win32con.CF_TEXT)
                if data:
                    text = data.decode("utf-8", errors="ignore").strip()
                    if not text:
                        return "📋 Clipboard mein text hai lekin khali hai (empty string)."
                    char_count = len(text)
                    line_count = text.count('\n') + 1
                    preview = text[:2000]
                    result = f"📋 **Clipboard Text (ANSI)**\n{'─' * 40}\n"
                    result += f"📏 Length: {char_count} chars | {line_count} lines\n"
                    result += f"{'─' * 40}\n{preview}"
                    if char_count > 2000:
                        result += f"\n\n[TRUNCATED — {char_count - 2000} aur characters hain]"
                    return result

            # Check if there's files instead of text
            if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_HDROP):
                return "📋 Clipboard mein text nahi hai — files copied hain. Use get_selected_file_context_tool instead."

            return "📋 Clipboard mein koi text nahi hai. Pehle kuch copy karo."

        finally:
            win32clipboard.CloseClipboard()

    except Exception as e:
        logger.error(f"Clipboard Read Error: {e}")
        try:
            win32clipboard.CloseClipboard()
        except Exception as _e:
            logger.debug("ignored Exception: %s", _e)
        return f"❌ Clipboard read karne mein error: {e}"


@function_tool
async def get_active_window_info_tool() -> str:
    """
    🪟 Currently active/foreground window ki info deta hai — title, process name, PID, position/size.
    Gets info about the currently active foreground window.
    Use when user says 'konsi window open hai', 'active app batao', 'foreground window kya hai'.
    """
    try:
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return "❌ Koi foreground window detect nahi hui."

        # Window title
        title = win32gui.GetWindowText(hwnd)

        # Window position and size
        try:
            rect = win32gui.GetWindowRect(hwnd)
            x, y, x2, y2 = rect
            width = x2 - x
            height = y2 - y
            pos_str = f"Position: ({x}, {y}) | Size: {width}x{height}px"
        except Exception:
            pos_str = "Position/Size: N/A"

        # Process ID and name
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            import psutil
            proc = psutil.Process(pid)
            proc_name = proc.name()
            proc_exe = proc.exe()
        except Exception:
            pid = "N/A"
            proc_name = "Unknown"
            proc_exe = "N/A"

        # Window class name
        try:
            class_name = win32gui.GetClassName(hwnd)
        except Exception:
            class_name = "Unknown"

        result = (
            f"🪟 **Active Window Info**\n"
            f"{'═' * 40}\n"
            f"📌 **Title**: {title if title else '(No Title)'}\n"
            f"🏷️ **Class**: {class_name}\n"
            f"⚙️ **Process**: {proc_name} (PID: {pid})\n"
            f"📂 **Exe Path**: {proc_exe}\n"
            f"📐 **{pos_str}**\n"
            f"🔑 **HWND**: {hwnd}"
        )
        return result

    except Exception as e:
        logger.error(f"Active Window Info Error: {e}")
        return f"❌ Active window info lene mein error: {e}"
