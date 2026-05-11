"""
Shell QR Code Tools v1.0
--------------------------
QR code generation and reading tools for Shell AI.
Generate, read, bulk create, and create WiFi QR codes.

Uses qrcode library for generation, pyzbar/opencv for reading.

Usage:
    from shell_safe_executor import god_tier_tool as function_tool
"""

import os
import logging
import re
from shell_safe_executor import god_tier_tool as function_tool

logger = logging.getLogger("shell_qr")


_DANGEROUS_QR_SCHEMES = ("javascript:", "file:", "data:", "vbscript:", "intent:")
_SUSPICIOUS_TLDS = (".ru", ".tk", ".xyz", ".cn", ".top")  # heuristic only


def _qr_risk_warning(data: str) -> str:
    """Return a human-readable warning string if the QR content looks risky.
    Empty string means the content appears benign.
    Detects: dangerous URL schemes, shortened URLs, bitcoin-request strings,
    commands that look like shell injection, obviously-punycode domains."""
    if not data:
        return ""
    low = data.strip().lower()
    for scheme in _DANGEROUS_QR_SCHEMES:
        if low.startswith(scheme):
            return f"QR uses dangerous scheme '{scheme}' — do NOT follow without review."
    if low.startswith("bitcoin:") or low.startswith("ethereum:"):
        return "QR is a crypto-payment request. Verify the address before sending."
    if re.match(r"^https?://(bit\.ly|tinyurl\.com|t\.co|goo\.gl|is\.gd|rb\.gy)/", low):
        return "QR is a shortened URL — final destination is hidden."
    if "xn--" in low:
        return "QR contains punycode — may be an IDN-spoofing lookalike domain."
    # Shell-injection-ish payloads (rare in QR but worth flagging).
    if any(bad in data for bad in ("`", "$(", "|sh", ";rm ")):
        return "QR contains shell metacharacters — do not pipe into a shell."
    return ""


# ================================================================
#  TOOL 1: GENERATE QR CODE
# ================================================================

@function_tool
async def qr_generate_tool(data: str, filename: str) -> str:
    """
    Generate a QR code image from text or URL data.
    Args:
        data: The text, URL, or data to encode in the QR code.
        filename: Output filename for the QR code image (e.g., 'myqr.png').
    """
    if not data or not data.strip():
        return "Error: No data provided to encode."

    if not filename:
        return "Error: No filename provided."

    # Ensure .png extension
    if not filename.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".gif")):
        filename += ".png"

    try:
        import qrcode
    except ImportError:
        return (
            "Error: qrcode library is not installed. "
            "Install it with: pip install qrcode[pil]"
        )

    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        os.makedirs(os.path.dirname(os.path.abspath(filename)), exist_ok=True)
        img.save(filename)

        file_size = os.path.getsize(filename)
        size_str = f"{file_size / 1024:.1f} KB" if file_size > 1024 else f"{file_size} B"

        data_preview = data[:100] + "..." if len(data) > 100 else data
        return (
            f"QR code generated successfully.\n"
            f"  File    : {os.path.abspath(filename)}\n"
            f"  Size    : {size_str}\n"
            f"  Data    : {data_preview}\n"
            f"  Data Len: {len(data)} characters"
        )
    except Exception as e:
        return f"Error generating QR code: {e}"


# ================================================================
#  TOOL 2: READ QR CODE
# ================================================================

@function_tool
async def qr_read_tool(image_path: str) -> str:
    """
    Read and decode a QR code from an image file.
    Args:
        image_path: Path to the image containing a QR code.
    """
    if not os.path.exists(image_path):
        return f"Error: File not found: {image_path}"

    # Try pyzbar first
    try:
        from pyzbar.pyzbar import decode as pyzbar_decode
        from PIL import Image

        img = Image.open(image_path)
        decoded = pyzbar_decode(img)

        if not decoded:
            return (
                f"No QR code found in '{os.path.basename(image_path)}'.\n"
                "Make sure the image contains a clear, readable QR code."
            )

        results = []
        for i, obj in enumerate(decoded, 1):
            data = obj.data.decode("utf-8", errors="replace")
            qr_type = obj.type
            rect = obj.rect
            # Content warning — scanned QR can carry phishing URLs or
            # javascript:/file:/data: schemes. Flag obvious risks so the
            # caller (and ultimately the user) doesn't blindly follow them.
            warning = _qr_risk_warning(data)
            results.append(
                f"  QR #{i}:\n"
                f"    Type    : {qr_type}\n"
                f"    Data    : {data}\n"
                f"    Position: x={rect.left}, y={rect.top}, w={rect.width}, h={rect.height}"
                + (f"\n    ⚠️ Warning: {warning}" if warning else "")
            )

        return (
            f"Found {len(decoded)} QR code(s) in '{os.path.basename(image_path)}':\n" +
            "\n".join(results)
        )
    except Exception as _e:
        logger.debug("ignored Exception: %s", _e)
    except Exception as e:
        logger.warning(f"pyzbar decode failed: {e}")

    # Try opencv
    try:
        import cv2

        img = cv2.imread(image_path)
        if img is None:
            return f"Error: Could not read image: {image_path}"

        detector = cv2.QRCodeDetector()
        data, bbox, _ = detector.detectAndDecode(img)

        if data:
            return (
                f"QR code decoded from '{os.path.basename(image_path)}':\n"
                f"  Data: {data}"
            )
        else:
            return (
                f"No QR code found in '{os.path.basename(image_path)}'.\n"
                "Make sure the image contains a clear, readable QR code."
            )
    except Exception as _e:
        logger.debug("ignored Exception: %s", _e)
    except Exception as e:
        logger.warning(f"opencv decode failed: {e}")

    return (
        "Error: No QR code reader library available.\n"
        "Install one of:\n"
        "  pip install pyzbar Pillow\n"
        "  pip install opencv-python"
    )


# ================================================================
#  TOOL 3: BULK GENERATE QR CODES
# ================================================================

@function_tool
async def qr_bulk_generate_tool(data_list: str, output_dir: str) -> str:
    """
    Generate multiple QR codes from a comma-separated list of data strings.
    Args:
        data_list: Comma-separated data entries (e.g., 'https://a.com, https://b.com, hello').
        output_dir: Directory where QR code images will be saved.
    """
    if not data_list or not data_list.strip():
        return "Error: No data provided. Use comma-separated values."

    try:
        import qrcode
    except ImportError:
        return (
            "Error: qrcode library is not installed. "
            "Install it with: pip install qrcode[pil]"
        )

    items = [item.strip() for item in data_list.split(",") if item.strip()]

    if not items:
        return "Error: No valid data items found after parsing."

    if len(items) > 100:
        return "Error: Maximum 100 QR codes at once. Please reduce the list."

    try:
        os.makedirs(output_dir, exist_ok=True)
        generated = []
        errors = []

        for i, data in enumerate(items, 1):
            try:
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_H,
                    box_size=10,
                    border=4,
                )
                qr.add_data(data)
                qr.make(fit=True)

                img = qr.make_image(fill_color="black", back_color="white")

                # Create safe filename
                safe_name = "".join(
                    c if c.isalnum() or c in "-_" else "_"
                    for c in data[:30]
                )
                filename = f"qr_{i:03d}_{safe_name}.png"
                filepath = os.path.join(output_dir, filename)
                img.save(filepath)
                generated.append((filename, data[:50]))
            except Exception as e:
                errors.append(f"  Item {i} ('{data[:30]}'): {e}")

        lines = [
            f"Bulk QR Generation Complete:",
            f"  Generated: {len(generated)}/{len(items)}",
            f"  Output Dir: {os.path.abspath(output_dir)}",
            f"{'=' * 40}",
        ]

        for fname, data_preview in generated:
            lines.append(f"  - {fname} -> {data_preview}")

        if errors:
            lines.append(f"\nErrors ({len(errors)}):")
            lines.extend(errors)

        return "\n".join(lines)
    except Exception as e:
        return f"Error in bulk QR generation: {e}"


# ================================================================
#  TOOL 4: WIFI QR CODE
# ================================================================

@function_tool
async def qr_wifi_tool(ssid: str, password: str, filename: str) -> str:
    """
    Generate a WiFi QR code that allows devices to connect by scanning.
    Args:
        ssid: WiFi network name (SSID).
        password: WiFi password. Use empty string for open networks.
        filename: Output filename for the QR code image.
    """
    if not ssid or not ssid.strip():
        return "Error: WiFi SSID (network name) is required."

    if not filename:
        return "Error: Output filename is required."

    if not filename.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".gif")):
        filename += ".png"

    try:
        import qrcode
    except ImportError:
        return (
            "Error: qrcode library is not installed. "
            "Install it with: pip install qrcode[pil]"
        )

    try:
        # Escape special characters in SSID and password
        def _escape_wifi(s: str) -> str:
            special = ['\\', '"', ';', ',', ':']
            for ch in special:
                s = s.replace(ch, f'\\{ch}')
            return s

        escaped_ssid = _escape_wifi(ssid)
        escaped_pass = _escape_wifi(password) if password else ""

        if password:
            auth_type = "WPA"
            wifi_string = f"WIFI:T:{auth_type};S:{escaped_ssid};P:{escaped_pass};;"
        else:
            auth_type = "nopass"
            wifi_string = f"WIFI:T:{auth_type};S:{escaped_ssid};;"

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )
        qr.add_data(wifi_string)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        os.makedirs(os.path.dirname(os.path.abspath(filename)), exist_ok=True)
        img.save(filename)

        file_size = os.path.getsize(filename)
        size_str = f"{file_size / 1024:.1f} KB" if file_size > 1024 else f"{file_size} B"

        return (
            f"WiFi QR code generated successfully.\n"
            f"  File     : {os.path.abspath(filename)}\n"
            f"  Size     : {size_str}\n"
            f"  SSID     : {ssid}\n"
            f"  Security : {'WPA/WPA2' if password else 'Open (no password)'}\n"
            f"  Scan this QR code with a phone camera to connect automatically."
        )
    except Exception as e:
        return f"Error generating WiFi QR code: {e}"
