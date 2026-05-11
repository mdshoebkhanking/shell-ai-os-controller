#!/usr/bin/env python3
"""
Shell OCR Tools — Optical Character Recognition utilities.
Uses pytesseract with easyocr fallback for text extraction from images and PDFs.
"""

import os
import logging
from shell_safe_executor import god_tier_tool as function_tool

logger = logging.getLogger("shell_ocr")


def _ocr_with_pytesseract(image):
    """Try OCR using pytesseract."""
    import pytesseract
    text = pytesseract.image_to_string(image)
    return text.strip(), "pytesseract"


def _ocr_with_easyocr(image_path: str):
    """Fallback OCR using easyocr."""
    import easyocr
    reader = easyocr.Reader(["en"], gpu=False)
    results = reader.readtext(image_path, detail=0)
    return "\n".join(results).strip(), "easyocr"


def _do_ocr(image_path: str) -> tuple:
    """Perform OCR with pytesseract first, then easyocr fallback."""
    from PIL import Image
    # Context manager guarantees the file handle + PIL buffer get released
    # even if grayscale conversion or the OCR backend raises mid-stream.
    with Image.open(image_path) as raw:
        img = raw.convert("L") if raw.mode != "L" else raw.copy()

    try:
        text, engine = _ocr_with_pytesseract(img)
        if text:
            return text, engine
    except ImportError:
        logger.debug("pytesseract not installed; trying easyocr")
    except Exception as e:
        # Separate the "tesseract binary missing" case so users get a
        # pointed message instead of a generic fallthrough.
        try:
            from pytesseract import TesseractNotFoundError
            if isinstance(e, TesseractNotFoundError):
                logger.warning(
                    "Tesseract binary not on PATH (install or set TESSERACT_CMD). "
                    "Falling back to easyocr."
                )
            else:
                logger.debug("pytesseract failed: %s", e)
        except ImportError:
            logger.debug("pytesseract failed: %s", e)

    try:
        text, engine = _ocr_with_easyocr(image_path)
        if text:
            return text, engine
    except ImportError:
        logger.debug("easyocr not installed")
    except Exception as e:
        logger.debug("easyocr failed: %s", e)

    return "", "none"


def _take_quick_screenshot(region=None) -> str:
    """Take a screenshot and return the temp file path."""
    import tempfile
    tmp = tempfile.mktemp(suffix=".png")
    try:
        import mss
        with mss.mss() as sct:
            monitor = region if region else sct.monitors[0]
            img = sct.grab(monitor)
            mss.tools.to_png(img.rgb, img.size, output=tmp)
    except ImportError:
        import pyautogui
        r = (region["left"], region["top"], region["width"], region["height"]) if region else None
        img = pyautogui.screenshot(region=r)
        img.save(tmp)
    return tmp


# ═══════════════════════════════════════════════════════════════
#  TOOL 1: OCR IMAGE
# ═══════════════════════════════════════════════════════════════

@function_tool
async def ocr_image_tool(image_path: str) -> str:
    """
    Extract text from an image file using OCR.
    Supports: PNG, JPG, BMP, TIFF, WEBP.
    Args:
        image_path: Path to the image file.
    """
    try:
        if not os.path.exists(image_path):
            return f"Error: File not found: {image_path}"

        text, engine = _do_ocr(image_path)
        if not text:
            return "No text detected in the image."

        char_count = len(text)
        word_count = len(text.split())
        line_count = len(text.splitlines())
        return (
            f"OCR Result (engine: {engine}):\n"
            f"Stats: {word_count} words, {char_count} chars, {line_count} lines\n"
            f"{'=' * 50}\n{text}"
        )
    except ImportError:
        return "Error: OCR requires pytesseract or easyocr. Install with: pip install pytesseract Pillow (or pip install easyocr)"
    except Exception as e:
        logger.error(f"OCR failed: {e}")
        return f"Error during OCR: {e}"


# ═══════════════════════════════════════════════════════════════
#  TOOL 2: OCR SCREENSHOT (capture + OCR in one step)
# ═══════════════════════════════════════════════════════════════

@function_tool
async def ocr_screenshot_tool() -> str:
    """
    Take a screenshot of the entire screen and immediately OCR it.
    Returns extracted text from whatever is currently on screen.
    """
    try:
        tmp_path = _take_quick_screenshot()
        try:
            text, engine = _do_ocr(tmp_path)
            if not text:
                return "Screenshot captured but no text detected on screen."
            word_count = len(text.split())
            return (
                f"Screen OCR (engine: {engine}) — {word_count} words detected:\n"
                f"{'=' * 50}\n{text}"
            )
        finally:
            try:
                os.unlink(tmp_path)
            except Exception as _e:
                logger.debug("ignored Exception: %s", _e)
    except Exception as e:
        logger.error(f"OCR screenshot failed: {e}")
        return f"Error during screen OCR: {e}"


# ═══════════════════════════════════════════════════════════════
#  TOOL 3: OCR REGION
# ═══════════════════════════════════════════════════════════════

@function_tool
async def ocr_region_tool(x: int, y: int, width: int, height: int) -> str:
    """
    OCR a specific region of the screen.
    Args:
        x: Left edge X coordinate.
        y: Top edge Y coordinate.
        width: Width of region in pixels.
        height: Height of region in pixels.
    """
    try:
        region = {"left": x, "top": y, "width": width, "height": height}
        tmp_path = _take_quick_screenshot(region=region)
        try:
            text, engine = _do_ocr(tmp_path)
            if not text:
                return f"No text detected in region ({x},{y}) {width}x{height}."
            word_count = len(text.split())
            return (
                f"Region OCR (engine: {engine}) — {word_count} words:\n"
                f"Region: x={x}, y={y}, {width}x{height}\n"
                f"{'=' * 50}\n{text}"
            )
        finally:
            try:
                os.unlink(tmp_path)
            except Exception as _e:
                logger.debug("ignored Exception: %s", _e)
    except Exception as e:
        logger.error(f"OCR region failed: {e}")
        return f"Error during region OCR: {e}"


# ═══════════════════════════════════════════════════════════════
#  TOOL 4: OCR PDF
# ═══════════════════════════════════════════════════════════════

@function_tool
async def ocr_pdf_tool(pdf_path: str) -> str:
    """
    Extract text from a scanned PDF by converting pages to images and OCR-ing them.
    For text-based PDFs, extracts embedded text directly first.
    Args:
        pdf_path: Path to the PDF file.
    """
    try:
        if not os.path.exists(pdf_path):
            return f"Error: File not found: {pdf_path}"
        if not pdf_path.lower().endswith(".pdf"):
            return "Error: File must be a PDF."

        all_text = []
        page_count = 0

        # First try direct text extraction with PyPDF2/pypdf
        try:
            from pypdf import PdfReader
            reader = PdfReader(pdf_path)
            for i, page in enumerate(reader.pages):
                txt = page.extract_text()
                if txt and txt.strip():
                    all_text.append(f"--- Page {i + 1} ---\n{txt.strip()}")
                    page_count += 1
            if all_text:
                combined = "\n\n".join(all_text)
                word_count = len(combined.split())
                return (
                    f"PDF Text Extraction (direct, {page_count} pages, {word_count} words):\n"
                    f"{'=' * 50}\n{combined}"
                )
        except ImportError:
            logger.debug("pypdf not available, trying image-based OCR")
        except Exception as e:
            logger.debug(f"Direct PDF extraction failed: {e}")

        # Fallback: convert pages to images and OCR
        try:
            from pdf2image import convert_from_path
            images = convert_from_path(pdf_path, dpi=200)
            for i, img in enumerate(images):
                import tempfile
                tmp = tempfile.mktemp(suffix=".png")
                img.save(tmp)
                try:
                    text, engine = _do_ocr(tmp)
                    if text:
                        all_text.append(f"--- Page {i + 1} (OCR: {engine}) ---\n{text}")
                        page_count += 1
                finally:
                    try:
                        os.unlink(tmp)
                    except Exception as _e:
                        logger.debug("ignored Exception: %s", _e)

            if all_text:
                combined = "\n\n".join(all_text)
                word_count = len(combined.split())
                return (
                    f"PDF OCR ({page_count} pages, {word_count} words):\n"
                    f"{'=' * 50}\n{combined}"
                )
            return "No text could be extracted from the PDF."
        except ImportError:
            return "Error: PDF OCR requires pdf2image + poppler. Install: pip install pdf2image pypdf"
    except Exception as e:
        logger.error(f"PDF OCR failed: {e}")
        return f"Error during PDF OCR: {e}"
