import os
import subprocess
import sys
import logging
import json
import time
import mimetypes
from datetime import datetime
from fuzzywuzzy import process
from shell_safe_executor import god_tier_tool as function_tool
import asyncio

try:
    import pygetwindow as gw
except ImportError:
    gw = None

sys.stdout.reconfigure(encoding='utf-8')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CACHE_FILE = "file_index_cache.json"
CACHE_EXPIRY_HOURS = 24

# File type groups for filtering
FILE_TYPE_GROUPS = {
    "images": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".ico", ".tiff", ".tif", ".heic", ".raw"},
    "videos": {".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".mpg", ".mpeg", ".3gp"},
    "documents": {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".rtf", ".odt", ".csv", ".md"},
    "audio": {".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a", ".opus"},
    "code": {".py", ".js", ".ts", ".html", ".css", ".java", ".cpp", ".c", ".go", ".rs", ".php", ".rb", ".json", ".xml", ".yaml", ".yml"},
    "archives": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"},
}


def _get_default_scan_dirs():
    """Get default directories to scan: Desktop, Documents, Downloads."""
    home = os.path.expanduser("~")
    dirs = [
        os.path.join(home, "Desktop"),
        os.path.join(home, "Documents"),
        os.path.join(home, "Downloads"),
    ]
    return [d for d in dirs if os.path.exists(d)]


def _format_size(size_bytes):
    """Format file size to human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def _get_file_type_extensions(file_type: str):
    """Get set of extensions for a file type group name."""
    file_type = file_type.lower().strip()
    # Try direct match
    if file_type in FILE_TYPE_GROUPS:
        return FILE_TYPE_GROUPS[file_type]
    # Try singular form
    for key, exts in FILE_TYPE_GROUPS.items():
        if file_type.rstrip("s") == key.rstrip("s"):
            return exts
    # Try as a single extension
    if file_type.startswith("."):
        return {file_type}
    return {f".{file_type}"}


async def focus_window(title_keyword: str) -> bool:
    if not gw:
        logger.warning("pygetwindow not available")
        return False

    await asyncio.sleep(1.5)
    title_keyword = title_keyword.lower().strip()

    for window in gw.getAllWindows():
        if title_keyword in window.title.lower():
            if window.isMinimized:
                window.restore()
            window.activate()
            logger.info(f"Window focused: {window.title}")
            return True
    logger.warning("Window not found for focus.")
    return False

async def index_files(base_dirs, force_refresh=False):
    # Check Cache
    if not force_refresh and os.path.exists(CACHE_FILE):
        try:
            mtime = os.path.getmtime(CACHE_FILE)
            if (time.time() - mtime) < (CACHE_EXPIRY_HOURS * 3600):
                logger.info("Loading file index from cache...")
                with open(CACHE_FILE, "r") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Cache load failed: {e}")

    logger.info("Building new file index (this may take time)...")
    file_index = []
    for base_dir in base_dirs:
        for root, _, files in os.walk(base_dir):
            for f in files:
                file_index.append({
                    "name": f,
                    "path": os.path.join(root, f),
                    "type": "file"
                })

    # Save Cache
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(file_index, f)
        logger.info(f"Indexed {len(file_index)} files and saved to cache.")
    except Exception as e:
        logger.error(f"Failed to save cache: {e}")

    return file_index

async def search_file(query, index):
    choices = [item["name"] for item in index if item.get("name")]
    if not choices:
        logger.warning("No files to match against.")
        return None

    result = process.extractOne(query, choices)
    if not result:
        return None
    best_match, score = result
    logger.info(f"Matched '{query}' to '{best_match}' (Score: {score})")
    if score > 70:
        for item in index:
            if item["name"] == best_match:
                return item
    return None

async def open_file(item):
    try:
        logger.info(f"Opening file: {item['path']}")
        if os.name == 'nt':
            os.startfile(item["path"])
        else:
            subprocess.call(['open' if sys.platform == 'darwin' else 'xdg-open', item["path"]])
        await focus_window(item["name"])
        return f"File opened: {item['name']}"
    except Exception as e:
        logger.error(f"Error opening file: {e}")
        return f"Failed to open file: {e}"

async def handle_command(command, index):
    item = await search_file(command, index)
    if item:
        return await open_file(item)
    else:
        logger.warning("File not found.")
        return "File not found."

@function_tool
async def Play_file(name: str) -> str:
    """
    Opens a file (video, music, doc) by fuzzy name search.
    Indexes available drives (Cached).
    """
    # Auto-detect available drives instead of hardcoding D:/
    folders_to_index = []
    if os.name == 'nt':
        for letter in "DCEFGH":
            drive = f"{letter}:/"
            if os.path.exists(drive):
                folders_to_index.append(drive)
                break  # Index first available non-C drive
    if not folders_to_index:
        folders_to_index = [os.path.expanduser("~")]

    command = name.strip()
    if not command:
        return "Please provide a file name to search."

    index = await index_files(folders_to_index)
    return await handle_command(command, index)

@function_tool
async def write_to_notepad_tool(text: str) -> str:
    """Creates a temporary notepad file with the given text."""
    try:
        import tempfile
        temp_file = os.path.join(tempfile.gettempdir(), "shell_temp_note.txt")
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(text)
        os.startfile(temp_file)
        return "Written to Notepad."
    except Exception as e:
        return f"Notepad fail: {e}"


# =========================================================
# NEW TOOLS
# =========================================================

@function_tool
async def search_files_tool(query: str, directory: str = "", file_type: str = "") -> str:
    """
    Searches for files by name with optional type filter using fuzzy matching.
    Scans Desktop/Documents/Downloads by default, or a specified directory.
    Shows path, size, and modified date for each match.

    Args:
        query: The filename (or partial name) to search for.
        directory: Optional directory to search in. Defaults to Desktop/Documents/Downloads.
        file_type: Optional file type filter (e.g., 'images', 'videos', 'documents', '.pdf', 'py').
    """
    if not query or not query.strip():
        return "Please provide a search query."

    query = query.strip()

    # Determine directories to scan
    if directory and directory.strip():
        scan_dirs = [directory.strip()]
        if not os.path.exists(scan_dirs[0]):
            return f"Directory not found: {scan_dirs[0]}"
    else:
        scan_dirs = _get_default_scan_dirs()
        if not scan_dirs:
            return "No default directories found (Desktop/Documents/Downloads)."

    # Get file type extensions filter
    type_extensions = None
    if file_type and file_type.strip():
        type_extensions = _get_file_type_extensions(file_type)

    # Collect all files
    all_files = []
    for scan_dir in scan_dirs:
        try:
            for root, _, files in os.walk(scan_dir):
                for f in files:
                    # Apply type filter
                    if type_extensions:
                        ext = os.path.splitext(f)[1].lower()
                        if ext not in type_extensions:
                            continue
                    full_path = os.path.join(root, f)
                    all_files.append({"name": f, "path": full_path})
        except PermissionError:
            continue

    if not all_files:
        filter_msg = f" (type: {file_type})" if file_type else ""
        return f"No files found{filter_msg} in the scanned directories."

    # Fuzzy match
    file_names = [f["name"] for f in all_files]
    matches = process.extract(query, file_names, limit=15)

    results = []
    seen_paths = set()
    for match_name, score in matches:
        if score < 50:
            continue
        for f in all_files:
            if f["name"] == match_name and f["path"] not in seen_paths:
                seen_paths.add(f["path"])
                try:
                    stat = os.stat(f["path"])
                    size = _format_size(stat.st_size)
                    modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
                except Exception:
                    size = "?"
                    modified = "?"
                results.append({
                    "name": f["name"],
                    "path": f["path"],
                    "size": size,
                    "modified": modified,
                    "score": score,
                })
                break  # Only first match per name

    if not results:
        return f"No files matching '{query}' found."

    lines = [f"Search results for '{query}':"]
    lines.append(f"{'Score':<7} {'Size':<10} {'Modified':<18} Path")
    lines.append("-" * 90)
    for r in results:
        lines.append(f"{r['score']:<7} {r['size']:<10} {r['modified']:<18} {r['path']}")
    lines.append(f"\nFound {len(results)} matching files.")
    return "\n".join(lines)


@function_tool
async def get_file_info_tool(file_path: str) -> str:
    """
    Gets detailed info about a file: size, created/modified dates, type, permissions, MIME type.
    If image: shows dimensions. If video: shows duration (if ffprobe available).

    Args:
        file_path: The full path to the file.
    """
    if not file_path or not file_path.strip():
        return "Please provide a file path."

    file_path = file_path.strip().replace('"', '')

    if not os.path.exists(file_path):
        return f"File not found: {file_path}"

    if os.path.isdir(file_path):
        return f"'{file_path}' is a directory, not a file. Use a file path."

    try:
        stat = os.stat(file_path)
        name = os.path.basename(file_path)
        ext = os.path.splitext(name)[1].lower()

        # Basic info
        size = _format_size(stat.st_size)
        size_bytes = stat.st_size
        created = datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
        modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        accessed = datetime.fromtimestamp(stat.st_atime).strftime("%Y-%m-%d %H:%M:%S")

        # MIME type
        mime_type, encoding = mimetypes.guess_type(file_path)
        mime_str = mime_type or "unknown"

        # Permissions
        import stat as stat_module
        mode = stat.st_mode
        perms = []
        if mode & stat_module.S_IRUSR: perms.append("read")
        if mode & stat_module.S_IWUSR: perms.append("write")
        if mode & stat_module.S_IXUSR: perms.append("execute")
        perm_str = ", ".join(perms) if perms else "none"

        # Determine file type category
        file_category = "Unknown"
        for cat, exts in FILE_TYPE_GROUPS.items():
            if ext in exts:
                file_category = cat.capitalize()
                break

        lines = [
            f"File Information: {name}",
            "-" * 50,
            f"  Path:          {file_path}",
            f"  Size:          {size} ({size_bytes:,} bytes)",
            f"  Type:          {file_category}",
            f"  Extension:     {ext or 'none'}",
            f"  MIME Type:     {mime_str}",
            f"  Created:       {created}",
            f"  Modified:      {modified}",
            f"  Last Accessed: {accessed}",
            f"  Permissions:   {perm_str}",
        ]

        # Image dimensions
        if ext in FILE_TYPE_GROUPS.get("images", set()):
            try:
                from PIL import Image
                with Image.open(file_path) as img:
                    w, h = img.size
                    img_mode = img.mode
                    lines.append(f"  Dimensions:    {w} x {h} px")
                    lines.append(f"  Color Mode:    {img_mode}")
            except ImportError:
                lines.append("  Dimensions:    (install Pillow for image dimensions)")
            except Exception as e:
                lines.append(f"  Dimensions:    Error reading image: {e}")

        # Video duration via ffprobe
        if ext in FILE_TYPE_GROUPS.get("videos", set()):
            try:
                import shutil
                if shutil.which("ffprobe"):
                    result = subprocess.run(
                        [
                            "ffprobe", "-v", "error",
                            "-show_entries", "format=duration",
                            "-of", "default=noprint_wrappers=1:nokey=1",
                            file_path
                        ],
                        capture_output=True, text=True, timeout=10
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        duration_sec = float(result.stdout.strip())
                        minutes = int(duration_sec // 60)
                        seconds = int(duration_sec % 60)
                        hours = int(minutes // 60)
                        minutes = minutes % 60
                        if hours > 0:
                            dur_str = f"{hours}h {minutes}m {seconds}s"
                        else:
                            dur_str = f"{minutes}m {seconds}s"
                        lines.append(f"  Duration:      {dur_str} ({duration_sec:.1f}s)")
                else:
                    lines.append("  Duration:      (install ffprobe for video duration)")
            except Exception as e:
                lines.append(f"  Duration:      Error: {e}")

        return "\n".join(lines)

    except Exception as e:
        return f"Error getting file info: {str(e)}"


@function_tool
async def recent_files_tool(count: int = 20, file_type: str = "") -> str:
    """
    Shows recently modified files from Desktop/Documents/Downloads.
    Optional type filter to show only specific file types.

    Args:
        count: Number of recent files to show (default 20, max 50).
        file_type: Optional type filter: 'images', 'videos', 'documents', 'audio', 'code', 'archives', or an extension like '.pdf'.
    """
    count = max(1, min(count, 50))

    scan_dirs = _get_default_scan_dirs()
    if not scan_dirs:
        return "No default directories found (Desktop/Documents/Downloads)."

    # Get type extensions filter
    type_extensions = None
    if file_type and file_type.strip():
        type_extensions = _get_file_type_extensions(file_type)

    # Collect all files with their modification times
    all_files = []
    for scan_dir in scan_dirs:
        try:
            for root, _, files in os.walk(scan_dir):
                for f in files:
                    # Apply type filter
                    if type_extensions:
                        ext = os.path.splitext(f)[1].lower()
                        if ext not in type_extensions:
                            continue
                    full_path = os.path.join(root, f)
                    try:
                        stat = os.stat(full_path)
                        all_files.append({
                            "name": f,
                            "path": full_path,
                            "size": stat.st_size,
                            "mtime": stat.st_mtime,
                        })
                    except (PermissionError, OSError):
                        continue
        except PermissionError:
            continue

    if not all_files:
        filter_msg = f" (type: {file_type})" if file_type else ""
        return f"No files found{filter_msg} in Desktop/Documents/Downloads."

    # Sort by modification time (newest first)
    all_files.sort(key=lambda x: x["mtime"], reverse=True)

    # Take top N
    recent = all_files[:count]

    filter_label = f" (type: {file_type})" if file_type else ""
    lines = [f"Recently modified files{filter_label}:"]
    lines.append(f"{'#':<4} {'Size':<10} {'Last Modified':<20} Name")
    lines.append("-" * 90)

    for i, f in enumerate(recent, 1):
        size_str = _format_size(f["size"])
        mod_str = datetime.fromtimestamp(f["mtime"]).strftime("%Y-%m-%d %H:%M:%S")
        lines.append(f"{i:<4} {size_str:<10} {mod_str:<20} {f['name']}")
        lines.append(f"     {f['path']}")

    lines.append(f"\nShowing {len(recent)} of {len(all_files)} files.")
    return "\n".join(lines)
