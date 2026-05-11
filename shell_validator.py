"""
Shell Validator - Input Validation & Sanitization
---------------------------------------------------
Common validators and sanitizers for all Shell AI tools.

Usage:
    from shell_validator import is_valid_email, sanitize_filename, is_safe_path
"""

import re
import os
from urllib.parse import urlparse


# ── Validators (return bool) ──────────────────────────────────────

_EMAIL_RE = re.compile(
    # Stricter per RFC 5321 intent: forbid consecutive dots and leading/
    # trailing dots in the local part, require at least one dot-label in
    # the domain, and cap TLD to letters only.
    r"^[a-zA-Z0-9_%+\-]+(\.[a-zA-Z0-9_%+\-]+)*"
    r"@[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?"
    r"(\.[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?)*"
    r"\.[a-zA-Z]{2,}$"
)

_PHONE_RE = re.compile(
    r"^\+?[1-9]\d{6,14}$"
)

_IP_RE = re.compile(
    r"^(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)$"
)


def is_valid_email(email: str) -> bool:
    """Validate email format."""
    if not email or not isinstance(email, str):
        return False
    return bool(_EMAIL_RE.match(email.strip()))


def is_valid_url(url: str) -> bool:
    """Validate URL has scheme and netloc."""
    if not url or not isinstance(url, str):
        return False
    try:
        result = urlparse(url.strip())
        return all([result.scheme in ("http", "https"), result.netloc])
    except Exception:
        return False


def is_safe_url(url: str) -> tuple[bool, str]:
    """Typed helper: reject non-http(s) schemes + private/loopback IPs.

    Returns (ok, reason). A reusable companion to `shell_downloader`'s
    internal `_validate_url` so any tool that accepts URL input can
    surface a consistent SSRF guard.
    """
    if not url or not isinstance(url, str):
        return False, "URL empty or not a string"
    try:
        parsed = urlparse(url.strip())
    except Exception as e:
        return False, f"urlparse failed: {e}"
    if parsed.scheme.lower() not in ("http", "https"):
        return False, f"scheme {parsed.scheme!r} not allowed (http/https only)"
    if not parsed.hostname:
        return False, "missing hostname"
    try:
        import ipaddress
        ip = ipaddress.ip_address(parsed.hostname)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return False, f"host {parsed.hostname!r} is loopback/private/link-local/reserved"
    except ValueError:
        # Not an IP literal — a DNS hostname. We don't resolve here to
        # avoid a blocking lookup; callers that need to enforce the IP
        # check should resolve first via a non-blocking resolver.
        pass
    return True, ""


def is_valid_phone(phone: str) -> bool:
    """Validate international phone number format."""
    if not phone or not isinstance(phone, str):
        return False
    cleaned = re.sub(r"[\s\-\(\)]", "", phone.strip())
    return bool(_PHONE_RE.match(cleaned))


def is_valid_file_path(path: str) -> bool:
    """Check if path string is a valid file path (doesn't need to exist)."""
    if not path or not isinstance(path, str):
        return False
    try:
        # Check for null bytes and obviously invalid chars
        if "\x00" in path:
            return False
        # Try normalizing
        os.path.normpath(path)
        return True
    except (ValueError, TypeError):
        return False


def is_safe_path(path: str, base_dir: str = None) -> bool:
    """Check path doesn't escape base_dir via traversal (e.g., ../)."""
    if not path or not isinstance(path, str):
        return False
    if ".." in path.replace("\\", "/"):
        return False
    if base_dir:
        resolved = os.path.realpath(os.path.join(base_dir, path))
        base_resolved = os.path.realpath(base_dir)
        return resolved.startswith(base_resolved)
    return True


def is_valid_ip(ip: str) -> bool:
    """Validate IPv4 address."""
    if not ip or not isinstance(ip, str):
        return False
    return bool(_IP_RE.match(ip.strip()))


def is_valid_port(port) -> bool:
    """Validate port number."""
    try:
        p = int(port)
        return 1 <= p <= 65535
    except (ValueError, TypeError):
        return False


# ── Sanitizers (return cleaned string) ────────────────────────────

_UNSAFE_FILENAME_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

# Windows reserved device names (case-insensitive)
_WINDOWS_RESERVED = frozenset({
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
})


def sanitize_filename(name: str, max_length: int = 200) -> str:
    """Remove unsafe characters from filename. Blocks Windows reserved names."""
    if not name:
        return "unnamed"
    cleaned = _UNSAFE_FILENAME_RE.sub("_", name.strip())
    cleaned = cleaned.strip(". ")
    if not cleaned:
        return "unnamed"
    # Block Windows reserved device names (with or without extension)
    base = cleaned.split(".")[0].upper()
    if base in _WINDOWS_RESERVED:
        cleaned = f"_{cleaned}"
    return cleaned[:max_length]


def sanitize_query(query: str, max_length: int = 500) -> str:
    """Trim, strip HTML tags, and clean a search/API query string."""
    if not query:
        return ""
    # Strip HTML tags to prevent XSS
    cleaned = re.sub(r"<[^>]+>", "", query)
    return cleaned.strip()[:max_length]


def sanitize_html(text: str) -> str:
    """Strip HTML tags from text."""
    if not text:
        return ""
    return re.sub(r"<[^>]+>", "", text)


def sanitize_command(cmd: str) -> str:
    """Remove shell metacharacters from a command string."""
    if not cmd:
        return ""
    return re.sub(r"[|&;`$><]", "", cmd)


# ── Package Name Validator ────────────────────────────────────────

_PACKAGE_RE = re.compile(r"^[a-zA-Z0-9_\-]+$")
_BLOCKED_PACKAGES = frozenset({
    "os", "sys", "subprocess", "shutil", "pathlib",
    "socket", "http", "ftplib", "smtplib", "ctypes",
    "importlib", "code", "codeop", "compile", "exec",
})


def is_safe_package_name(name: str) -> bool:
    """Validate pip package name is safe to install."""
    if not name or not isinstance(name, str):
        return False
    name = name.strip().split("[")[0].split("==")[0].split(">=")[0].split("<=")[0]
    if not _PACKAGE_RE.match(name):
        return False
    if name.lower() in _BLOCKED_PACKAGES:
        return False
    return True


# ── Voice/Text Command Validation ────────────────────────────────

# Patterns that should be blocked in voice/text commands
_DANGEROUS_COMMAND_PATTERNS = [
    re.compile(r"rm\s+(-rf?\s+)?/", re.IGNORECASE),           # rm -rf /
    re.compile(r"format\s+[a-z]:", re.IGNORECASE),             # format C:
    re.compile(r"del\s+/[sfq]\s+", re.IGNORECASE),            # del /s /f /q
    re.compile(r":(){ :\|:& };:", re.IGNORECASE),             # fork bomb
    re.compile(r">\s*/dev/(sda|null)", re.IGNORECASE),         # disk write
    re.compile(r"mkfs\.", re.IGNORECASE),                      # filesystem format
    re.compile(r"dd\s+if=.+of=/dev/", re.IGNORECASE),         # dd disk overwrite
]

# Max length for a single voice command
_MAX_COMMAND_LENGTH = 5000


def sanitize_voice_command(text: str) -> tuple:
    """
    Validate and sanitize a voice/text command input.
    Returns: (sanitized_text, is_safe, warning_message)

    - Strips control characters and null bytes
    - Checks for dangerously long input
    - Detects destructive OS commands
    - Strips embedded HTML/script tags
    """
    if not text or not isinstance(text, str):
        return "", True, ""

    # Strip null bytes and control characters (except newline/tab)
    cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)

    # Strip HTML/script tags
    cleaned = re.sub(r'<script[^>]*>.*?</script>', '', cleaned, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r'<[^>]+>', '', cleaned)

    # Length check
    if len(cleaned) > _MAX_COMMAND_LENGTH:
        cleaned = cleaned[:_MAX_COMMAND_LENGTH]
        return cleaned, True, f"Command truncated to {_MAX_COMMAND_LENGTH} characters."

    # Check for dangerous patterns
    for pattern in _DANGEROUS_COMMAND_PATTERNS:
        if pattern.search(cleaned):
            return cleaned, False, f"Potentially destructive command detected: {pattern.pattern}"

    return cleaned.strip(), True, ""


def validate_tool_input(value: str, input_type: str = "text", max_length: int = 1000) -> tuple:
    """
    Generic input validator for tool parameters.
    Returns: (cleaned_value, is_valid, error_message)

    input_type: "text", "email", "url", "path", "phone", "number"
    """
    if not value or not isinstance(value, str):
        return "", False, "Input is empty or invalid type."

    value = value.strip()

    if len(value) > max_length:
        return value[:max_length], False, f"Input exceeds {max_length} character limit."

    if input_type == "email":
        if is_valid_email(value):
            return value, True, ""
        return value, False, "Invalid email format."

    elif input_type == "url":
        if is_valid_url(value):
            return value, True, ""
        return value, False, "Invalid URL format. Must start with http:// or https://"

    elif input_type == "path":
        if is_safe_path(value):
            return value, True, ""
        return value, False, "Unsafe path detected (directory traversal)."

    elif input_type == "phone":
        if is_valid_phone(value):
            return value, True, ""
        return value, False, "Invalid phone number format."

    elif input_type == "number":
        try:
            float(value)
            return value, True, ""
        except ValueError:
            return value, False, "Invalid number format."

    # Default: text — just sanitize
    sanitized = sanitize_query(value, max_length=max_length)
    return sanitized, True, ""
