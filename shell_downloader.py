#!/usr/bin/env python3
"""
Shell Downloader Tools — Download files, get info, and grab YouTube audio
"""
import os
import ipaddress
import logging
import asyncio
import socket
from pathlib import Path
from urllib.parse import urlparse, urljoin

from shell_safe_executor import god_tier_tool as function_tool

logger = logging.getLogger("shell_downloader")


# ─────────────────────────────────────────────────────────────────────
# URL validation (SSRF defense)
# ─────────────────────────────────────────────────────────────────────

_ALLOWED_URL_SCHEMES = frozenset(("http", "https"))
_REDIRECT_STATUSES = frozenset((301, 302, 303, 307, 308))
_MAX_REDIRECTS = 5


def _truthy(value) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _blocked_ip(ip: ipaddress._BaseAddress) -> bool:
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_unspecified
        or ip.is_multicast
    )


def _is_private_or_loopback_host(hostname: str) -> bool:
    """True if hostname is or resolves to a blocked internal IP."""
    if not hostname:
        return True
    h = hostname.strip().lower()
    if h in ("localhost", "ip6-localhost", "ip6-loopback"):
        return True
    try:
        ip = ipaddress.ip_address(h)
        return _blocked_ip(ip)
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(h, None, type=socket.SOCK_STREAM)
    except OSError:
        return True
    if not infos:
        return True
    for info in infos:
        try:
            if _blocked_ip(ipaddress.ip_address(info[4][0])):
                return True
        except ValueError:
            return True
    return False


def _validate_url(url: str) -> tuple[bool, str]:
    """Gate on URL scheme and loopback/private IP host.
    Blocks file://, gopher://, ftp://, javascript:, data:, plus obvious
    SSRF targets like 127.0.0.1 and RFC1918 ranges.
    """
    if not url or not isinstance(url, str):
        return False, "url must be a non-empty string"
    parsed = urlparse(url.strip())
    if parsed.scheme.lower() not in _ALLOWED_URL_SCHEMES:
        return False, f"scheme {parsed.scheme!r} not allowed (http/https only)"
    if not parsed.hostname:
        return False, "missing hostname"
    if _is_private_or_loopback_host(parsed.hostname):
        return False, f"host {parsed.hostname!r} is loopback/private/link-local"
    return True, ""


def _resolve_save_path(path: str) -> tuple:
    """Resolve download targets into SHELL_DOWNLOAD_DIR unless explicitly allowed."""
    requested = str(path or "").strip()
    if not requested:
        return None, "save path cannot be empty"
    if _truthy(os.getenv("SHELL_ALLOW_ARBITRARY_DOWNLOAD_PATH")):
        return requested, ""

    base = Path(os.getenv("SHELL_DOWNLOAD_DIR", "shell_downloads")).expanduser().resolve()
    target = Path(requested).expanduser()
    if target.is_absolute():
        resolved_abs = target.resolve()
        if resolved_abs == base or base in resolved_abs.parents:
            return str(resolved_abs), ""
        target = base / target.name
    else:
        target = base / target
    resolved = target.resolve()
    if resolved != base and base not in resolved.parents:
        return None, f"save path escapes download directory {base}"
    return str(resolved), ""


def _resolve_save_dir(path: str) -> tuple:
    requested = str(path or "").strip() or "downloads"
    if _truthy(os.getenv("SHELL_ALLOW_ARBITRARY_DOWNLOAD_PATH")):
        return requested, ""

    base = Path(os.getenv("SHELL_DOWNLOAD_DIR", "shell_downloads")).expanduser().resolve()
    target = Path(requested).expanduser()
    if target.is_absolute():
        target = base / target.name
    else:
        target = base / target
    resolved = target.resolve()
    if resolved != base and base not in resolved.parents:
        return None, f"save directory escapes download directory {base}"
    return str(resolved), ""


def _safe_filename_from_url(url: str, fallback: str) -> str:
    parsed = urlparse(url)
    name = os.path.basename(parsed.path.rstrip("/")) or fallback
    name = name.replace("\\", "_").replace("/", "_").strip()
    if name in {"", ".", ".."}:
        return fallback
    return name


async def _httpx_request_with_safe_redirects(client, method: str, url: str):
    current = url
    for _ in range(_MAX_REDIRECTS + 1):
        ok, reason = _validate_url(current)
        if not ok:
            raise ValueError(f"URL rejected: {reason}")
        response = await client.request(method, current, follow_redirects=False)
        if response.status_code in _REDIRECT_STATUSES:
            location = response.headers.get("location")
            if not location:
                return response, current
            current = urljoin(str(response.url), location)
            continue
        return response, current
    raise ValueError(f"too many redirects (>{_MAX_REDIRECTS})")


def _urllib_open_with_safe_redirects(method: str, url: str, timeout: int):
    import urllib.error
    import urllib.request

    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    opener = urllib.request.build_opener(_NoRedirect)
    current = url
    for _ in range(_MAX_REDIRECTS + 1):
        ok, reason = _validate_url(current)
        if not ok:
            raise ValueError(f"URL rejected: {reason}")
        req = urllib.request.Request(
            current,
            method=method,
            headers={"User-Agent": "Shell-AI-Downloader/1.0"},
        )
        try:
            return opener.open(req, timeout=timeout), current
        except urllib.error.HTTPError as e:
            if e.code in _REDIRECT_STATUSES:
                location = e.headers.get("Location")
                if not location:
                    raise
                current = urljoin(current, location)
                continue
            raise
    raise ValueError(f"too many redirects (>{_MAX_REDIRECTS})")


def _human_size(size_bytes: int) -> str:
    """Convert bytes to human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


async def _download_single(url: str, save_path: str) -> dict:
    """Download a single file. Returns dict with status info."""
    ok, reason = _validate_url(url)
    if not ok:
        logger.warning("download rejected: %s (url=%s)", reason, url)
        return {"success": False, "error": f"URL rejected: {reason}"}
    resolved_path, path_error = _resolve_save_path(save_path)
    if not resolved_path:
        return {"success": False, "error": f"Save path rejected: {path_error}"}
    try:
        # Try httpx first (async-native)
        try:
            import httpx
            async with httpx.AsyncClient(timeout=120.0) as client:
                response, _final_url = await _httpx_request_with_safe_redirects(client, "GET", url)
                response.raise_for_status()
                data = response.content
                content_type = response.headers.get("content-type", "unknown")
        except ImportError:
            # Fallback to urllib (sync, run in thread)
            loop = asyncio.get_event_loop()
            def _fetch():
                with _urllib_open_with_safe_redirects("GET", url, 120)[0] as resp:
                    return resp.read(), resp.headers.get("Content-Type", "unknown")
            data, content_type = await loop.run_in_executor(None, _fetch)

        os.makedirs(os.path.dirname(resolved_path) or ".", exist_ok=True)
        with open(resolved_path, "wb") as f:
            f.write(data)
        return {"success": True, "path": resolved_path, "size": len(data), "type": content_type}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════
#  TOOL 1: DOWNLOAD FILE
# ═══════════════════════════════════════════════════════════════

@function_tool
async def download_file_tool(url: str, save_path: str) -> str:
    """
    Download a file from a URL and save it locally.
    Uses httpx if available, otherwise falls back to urllib.
    Args:
        url: The URL to download from.
        save_path: Local file path to save the downloaded file.
    """
    result = await _download_single(url, save_path)
    if result["success"]:
        return (
            f"Download successful.\n"
            f"URL: {url}\n"
            f"Saved to: {result['path']}\n"
            f"Size: {_human_size(result['size'])}\n"
            f"Type: {result['type']}"
        )
    else:
        return f"Download failed.\nURL: {url}\nError: {result['error']}"


# ═══════════════════════════════════════════════════════════════
#  TOOL 2: DOWNLOAD MULTIPLE FILES
# ═══════════════════════════════════════════════════════════════

@function_tool
async def download_multiple_tool(urls: str, save_dir: str) -> str:
    """
    Download multiple files from comma-separated URLs.
    Files are saved with their original filenames into the specified directory.
    Args:
        urls: Comma-separated list of URLs to download.
        save_dir: Directory to save downloaded files.
    """
    url_list = [u.strip() for u in urls.split(",") if u.strip()]
    if not url_list:
        return "No valid URLs provided."
    safe_dir, path_error = _resolve_save_dir(save_dir)
    if not safe_dir:
        return f"Save directory rejected: {path_error}"
    os.makedirs(safe_dir, exist_ok=True)
    results = []
    success_count = 0
    fail_count = 0
    for url in url_list:
        filename = _safe_filename_from_url(url, f"download_{url_list.index(url)}")
        save_path = os.path.join(safe_dir, filename)
        result = await _download_single(url, save_path)
        if result["success"]:
            success_count += 1
            results.append(f"  OK: {filename} ({_human_size(result['size'])})")
        else:
            fail_count += 1
            results.append(f"  FAIL: {filename} — {result['error']}")
    header = (
        f"Download complete: {success_count} succeeded, {fail_count} failed\n"
        f"Save directory: {safe_dir}\n"
    )
    return header + "\n".join(results)


# ═══════════════════════════════════════════════════════════════
#  TOOL 3: GET DOWNLOAD INFO (HEAD request)
# ═══════════════════════════════════════════════════════════════

@function_tool
async def download_info_tool(url: str) -> str:
    """
    Get file information from a URL without downloading it (HTTP HEAD request).
    Returns file size, content type, filename, and server info.
    Args:
        url: The URL to inspect.
    """
    ok, reason = _validate_url(url)
    if not ok:
        logger.warning("download info rejected: %s (url=%s)", reason, url)
        return f"URL rejected: {reason}"

    try:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=30.0) as client:
                response, url = await _httpx_request_with_safe_redirects(client, "HEAD", url)
                headers = dict(response.headers)
                status = response.status_code
        except ImportError:
            loop = asyncio.get_event_loop()
            def _head():
                with _urllib_open_with_safe_redirects("HEAD", url, 30)[0] as resp:
                    return dict(resp.headers), resp.status, resp.geturl()
            headers, status, url = await loop.run_in_executor(None, _head)

        content_length = headers.get("content-length", headers.get("Content-Length", "unknown"))
        content_type = headers.get("content-type", headers.get("Content-Type", "unknown"))
        server = headers.get("server", headers.get("Server", "unknown"))

        # Try to extract filename
        cd = headers.get("content-disposition", headers.get("Content-Disposition", ""))
        filename = "unknown"
        if "filename=" in cd:
            filename = cd.split("filename=")[-1].strip('" ')
        else:
            filename = url.rstrip("/").split("/")[-1].split("?")[0] or "unknown"

        size_str = "unknown"
        if content_length and content_length != "unknown":
            try:
                size_str = _human_size(int(content_length))
            except ValueError:
                size_str = content_length

        return (
            f"URL: {url}\n"
            f"Status: {status}\n"
            f"Filename: {filename}\n"
            f"Content-Type: {content_type}\n"
            f"Size: {size_str}\n"
            f"Server: {server}"
        )
    except Exception as e:
        return f"Failed to get info for URL.\nURL: {url}\nError: {e}"


# ═══════════════════════════════════════════════════════════════
#  TOOL 4: DOWNLOAD YOUTUBE AUDIO (yt-dlp)
# ═══════════════════════════════════════════════════════════════

@function_tool
async def download_youtube_audio_tool(url: str, save_dir: str) -> str:
    """
    Download audio from a YouTube video using yt-dlp.
    Extracts audio in the best available quality as MP3/M4A.
    Args:
        url: YouTube video URL.
        save_dir: Directory to save the audio file.
    """
    try:
        import yt_dlp
    except ImportError:
        return (
            "yt-dlp is not installed.\n"
            "Install it with: pip install yt-dlp\n"
            "Then try again."
        )
    try:
        os.makedirs(save_dir, exist_ok=True)
        output_template = os.path.join(save_dir, "%(title)s.%(ext)s")
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": output_template,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
            "quiet": True,
            "no_warnings": True,
        }
        loop = asyncio.get_event_loop()
        def _download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return info
        info = await loop.run_in_executor(None, _download)
        title = info.get("title", "Unknown")
        duration = info.get("duration", 0)
        mins = duration // 60
        secs = duration % 60
        # Find the downloaded file
        expected_file = os.path.join(save_dir, f"{info.get('title', 'audio')}.mp3")
        file_size = "unknown"
        if os.path.isfile(expected_file):
            file_size = _human_size(os.path.getsize(expected_file))
        return (
            f"YouTube audio downloaded successfully.\n"
            f"Title: {title}\n"
            f"Duration: {mins}:{secs:02d}\n"
            f"Format: MP3 (192kbps)\n"
            f"Size: {file_size}\n"
            f"Saved to: {save_dir}"
        )
    except Exception as e:
        error_msg = str(e)
        if "ffmpeg" in error_msg.lower() or "ffprobe" in error_msg.lower():
            return (
                f"Download failed: FFmpeg is required for audio extraction.\n"
                f"Install FFmpeg and ensure it is on your PATH.\n"
                f"Error: {error_msg}"
            )
        return f"YouTube audio download failed.\nURL: {url}\nError: {error_msg}"
