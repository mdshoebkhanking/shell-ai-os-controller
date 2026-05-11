"""
Shell PDF Tools v1.0
---------------------
PDF manipulation tools for Shell AI.
Extract text, merge, split, get info, convert to images, and password protect PDFs.

Usage:
    from shell_safe_executor import god_tier_tool as function_tool
"""

import os
import logging
from shell_safe_executor import god_tier_tool as function_tool

logger = logging.getLogger("shell_pdf")


def _get_file_size_str(path: str) -> str:
    """Returns human-readable file size."""
    size = os.path.getsize(path)
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    else:
        return f"{size / (1024 * 1024):.2f} MB"


# ================================================================
#  TOOL 1: EXTRACT TEXT FROM PDF
# ================================================================

@function_tool
async def pdf_extract_text_tool(filepath: str) -> str:
    """
    Extract all text content from a PDF file.
    Args:
        filepath: Path to the PDF file.
    Returns:
        Extracted text from all pages.
    """
    if not os.path.exists(filepath):
        return f"Error: File not found: {filepath}"

    try:
        from PyPDF2 import PdfReader
    except ImportError:
        return (
            "Error: PyPDF2 is not installed. "
            "Install it with: pip install PyPDF2"
        )

    try:
        reader = PdfReader(filepath)
        total_pages = len(reader.pages)

        if total_pages == 0:
            return "Error: PDF has no pages."

        all_text = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text and text.strip():
                all_text.append(f"--- Page {i + 1} ---\n{text.strip()}")

        if not all_text:
            return (
                f"PDF has {total_pages} pages but no extractable text. "
                "The PDF may contain scanned images instead of text."
            )

        result = "\n\n".join(all_text)
        return (
            f"Extracted text from {total_pages} pages of '{os.path.basename(filepath)}':\n\n"
            f"{result}"
        )
    except Exception as e:
        return f"Error extracting text from PDF: {e}"


# ================================================================
#  TOOL 2: MERGE TWO PDFs
# ================================================================

@function_tool
async def pdf_merge_tool(file1: str, file2: str, output: str) -> str:
    """
    Merge two PDF files into one.
    Args:
        file1: Path to the first PDF.
        file2: Path to the second PDF.
        output: Path for the merged output PDF.
    """
    for path in [file1, file2]:
        if not os.path.exists(path):
            return f"Error: File not found: {path}"

    try:
        from PyPDF2 import PdfMerger
    except ImportError:
        try:
            from PyPDF2 import PdfWriter, PdfReader
        except ImportError:
            return (
                "Error: PyPDF2 is not installed. "
                "Install it with: pip install PyPDF2"
            )

        try:
            writer = PdfWriter()
            for pdf_path in [file1, file2]:
                reader = PdfReader(pdf_path)
                for page in reader.pages:
                    writer.add_page(page)

            os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
            with open(output, "wb") as f:
                writer.write(f)

            return (
                f"Successfully merged PDFs:\n"
                f"  1. {os.path.basename(file1)}\n"
                f"  2. {os.path.basename(file2)}\n"
                f"  Output: {output} ({_get_file_size_str(output)})"
            )
        except Exception as e:
            return f"Error merging PDFs: {e}"

    try:
        merger = PdfMerger()
        merger.append(file1)
        merger.append(file2)

        os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
        merger.write(output)
        merger.close()

        return (
            f"Successfully merged PDFs:\n"
            f"  1. {os.path.basename(file1)}\n"
            f"  2. {os.path.basename(file2)}\n"
            f"  Output: {output} ({_get_file_size_str(output)})"
        )
    except Exception as e:
        return f"Error merging PDFs: {e}"


# ================================================================
#  TOOL 3: SPLIT PDF (EXTRACT PAGE RANGE)
# ================================================================

@function_tool
async def pdf_split_tool(filepath: str, start_page: int, end_page: int, output: str) -> str:
    """
    Extract a range of pages from a PDF into a new file.
    Args:
        filepath: Path to the source PDF.
        start_page: Starting page number (1-based).
        end_page: Ending page number (1-based, inclusive).
        output: Path for the output PDF.
    """
    if not os.path.exists(filepath):
        return f"Error: File not found: {filepath}"

    try:
        from PyPDF2 import PdfReader, PdfWriter
    except ImportError:
        return (
            "Error: PyPDF2 is not installed. "
            "Install it with: pip install PyPDF2"
        )

    try:
        reader = PdfReader(filepath)
        total_pages = len(reader.pages)

        if start_page < 1 or end_page < 1:
            return "Error: Page numbers must be >= 1."
        if start_page > total_pages or end_page > total_pages:
            return f"Error: PDF only has {total_pages} pages. Requested range {start_page}-{end_page} is out of bounds."
        if start_page > end_page:
            return "Error: start_page must be <= end_page."

        writer = PdfWriter()
        for i in range(start_page - 1, end_page):
            writer.add_page(reader.pages[i])

        os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
        with open(output, "wb") as f:
            writer.write(f)

        pages_extracted = end_page - start_page + 1
        return (
            f"Successfully extracted pages {start_page}-{end_page} "
            f"({pages_extracted} pages) from '{os.path.basename(filepath)}'.\n"
            f"Output: {output} ({_get_file_size_str(output)})"
        )
    except Exception as e:
        return f"Error splitting PDF: {e}"


# ================================================================
#  TOOL 4: PDF INFO / METADATA
# ================================================================

@function_tool
async def pdf_info_tool(filepath: str) -> str:
    """
    Get PDF metadata including page count, file size, author, title, and more.
    Args:
        filepath: Path to the PDF file.
    """
    if not os.path.exists(filepath):
        return f"Error: File not found: {filepath}"

    try:
        from PyPDF2 import PdfReader
    except ImportError:
        return (
            "Error: PyPDF2 is not installed. "
            "Install it with: pip install PyPDF2"
        )

    try:
        reader = PdfReader(filepath)
        meta = reader.metadata
        total_pages = len(reader.pages)
        file_size = _get_file_size_str(filepath)

        # Get page dimensions from first page
        first_page = reader.pages[0] if total_pages > 0 else None
        dimensions = "Unknown"
        if first_page:
            box = first_page.mediabox
            w = float(box.width) / 72.0  # points to inches
            h = float(box.height) / 72.0
            dimensions = f"{w:.1f} x {h:.1f} inches ({float(box.width):.0f} x {float(box.height):.0f} points)"

        is_encrypted = reader.is_encrypted

        info_lines = [
            f"PDF Info: {os.path.basename(filepath)}",
            f"{'=' * 40}",
            f"  File Size  : {file_size}",
            f"  Pages      : {total_pages}",
            f"  Page Size  : {dimensions}",
            f"  Encrypted  : {'Yes' if is_encrypted else 'No'}",
        ]

        if meta:
            info_lines.append(f"  Title      : {meta.title or 'N/A'}")
            info_lines.append(f"  Author     : {meta.author or 'N/A'}")
            info_lines.append(f"  Subject    : {meta.subject or 'N/A'}")
            info_lines.append(f"  Creator    : {meta.creator or 'N/A'}")
            info_lines.append(f"  Producer   : {meta.producer or 'N/A'}")
            if meta.creation_date:
                info_lines.append(f"  Created    : {meta.creation_date}")
            if meta.modification_date:
                info_lines.append(f"  Modified   : {meta.modification_date}")

        return "\n".join(info_lines)
    except Exception as e:
        return f"Error reading PDF info: {e}"


# ================================================================
#  TOOL 5: PDF TO IMAGES
# ================================================================

@function_tool
async def pdf_to_images_tool(filepath: str, output_dir: str) -> str:
    """
    Convert each page of a PDF to an image (PNG).
    Args:
        filepath: Path to the PDF file.
        output_dir: Directory where images will be saved.
    """
    if not os.path.exists(filepath):
        return f"Error: File not found: {filepath}"

    try:
        from pdf2image import convert_from_path
    except ImportError:
        return (
            "Error: pdf2image is not installed. "
            "Install it with: pip install pdf2image\n"
            "Also requires poppler. On Windows: choco install poppler\n"
            "On Linux: sudo apt-get install poppler-utils"
        )

    try:
        os.makedirs(output_dir, exist_ok=True)
        images = convert_from_path(filepath)

        saved_files = []
        base_name = os.path.splitext(os.path.basename(filepath))[0]

        for i, image in enumerate(images):
            img_path = os.path.join(output_dir, f"{base_name}_page_{i + 1}.png")
            image.save(img_path, "PNG")
            saved_files.append(img_path)

        return (
            f"Successfully converted {len(saved_files)} pages to images.\n"
            f"Output directory: {output_dir}\n"
            f"Files:\n" +
            "\n".join(f"  - {os.path.basename(f)}" for f in saved_files)
        )
    except Exception as e:
        return f"Error converting PDF to images: {e}"


# ================================================================
#  TOOL 6: PASSWORD PROTECT PDF
# ================================================================

@function_tool
async def pdf_protect_tool(filepath: str, password: str) -> str:
    """
    Password protect a PDF file. Creates a new encrypted copy.
    Args:
        filepath: Path to the PDF file.
        password: Password to set on the PDF.
    """
    if not os.path.exists(filepath):
        return f"Error: File not found: {filepath}"

    if not password or len(password) < 1:
        return "Error: Password cannot be empty."

    try:
        from PyPDF2 import PdfReader, PdfWriter
    except ImportError:
        return (
            "Error: PyPDF2 is not installed. "
            "Install it with: pip install PyPDF2"
        )

    try:
        reader = PdfReader(filepath)
        writer = PdfWriter()

        for page in reader.pages:
            writer.add_page(page)

        # Use a strong random owner password so only the user (who knows
        # the supplied `password`) can open the PDF, while a different
        # owner-side key controls print/modify/extract permissions.
        # PyPDF2 ≥3 exposes `use_128bit` for AES — older versions may
        # silently fall back to 40-bit RC4.
        import secrets
        owner_pw = secrets.token_urlsafe(32)
        try:
            writer.encrypt(user_password=password, owner_password=owner_pw, use_128bit=True)
        except TypeError:
            # Very old PyPDF2 — positional signature only, no permissions.
            writer.encrypt(password)

        # Save to a new file with _protected suffix
        base, ext = os.path.splitext(filepath)
        output_path = f"{base}_protected{ext}"

        with open(output_path, "wb") as f:
            writer.write(f)

        return (
            f"Successfully password-protected PDF.\n"
            f"  Source : {os.path.basename(filepath)}\n"
            f"  Output : {output_path}\n"
            f"  Size   : {_get_file_size_str(output_path)}\n"
            f"  Password is set. Do not forget it!"
        )
    except Exception as e:
        return f"Error protecting PDF: {e}"
