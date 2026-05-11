#!/usr/bin/env python3
import os
import logging
from typing import List, Union
from PIL import Image
from shell_safe_executor import god_tier_tool as function_tool

logger = logging.getLogger("shell_converter")


def _get_file_size_str(path: str) -> str:
    """Returns human-readable file size."""
    size = os.path.getsize(path)
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    else:
        return f"{size / (1024 * 1024):.2f} MB"


# ═══════════════════════════════════════════════════════════════
#  TOOL 1: UNIVERSAL PDF CONVERTER (UPGRADED)
# ═══════════════════════════════════════════════════════════════

@function_tool
async def convert_to_pdf_tool(input_paths: Union[str, List[str]], output_name: str = "converted_doc") -> str:
    """
    UNIVERSAL PDF CONVERTER (v2.0 - Upgraded).
    Converts Images (JPG, PNG), Text (TXT, MD, PY), Documents (DOCX),
    HTML files, and Spreadsheets (XLSX, CSV) to a single PDF.
    Args:
        input_paths: A single file path or list of file paths.
        output_name: Name of the output PDF (e.g., "my_report").
    """
    try:
        # Normalize input
        if isinstance(input_paths, str):
            input_paths = [input_paths]

        # Filter existing files
        valid_paths = [p for p in input_paths if os.path.exists(p)]
        missing = [p for p in input_paths if not os.path.exists(p)]

        if missing:
            logger.warning(f"Missing files skipped: {missing}")

        if not valid_paths:
            return "❌ Error: Koi valid file nahi mili. Check karo ke path sahi hai aur file exist karti hai."

        # Determine output path
        home = os.path.expanduser("~")
        target_dir = os.path.join(home, "Documents", "Shell_PDFs")
        os.makedirs(target_dir, exist_ok=True)
        pdf_path = os.path.join(target_dir, f"{output_name}.pdf")

        # Check types
        exts = {os.path.splitext(p)[1].lower() for p in valid_paths}
        result = ""

        # MODE 1: IMAGES ONLY
        if all(e in ['.jpg', '.jpeg', '.png', '.bmp', '.webp', '.gif', '.tiff', '.ico'] for e in exts):
            result = _convert_images_to_pdf(valid_paths, pdf_path)

        # MODE 2: TEXT FILES (TXT, MD, PY, LOG, etc.)
        elif all(e in ['.txt', '.md', '.py', '.js', '.json', '.log', '.ini', '.bat', '.cfg', '.yaml', '.yml', '.toml', '.xml', '.css'] for e in exts):
            result = _convert_text_to_pdf(valid_paths, pdf_path)

        # MODE 3: DOCX (Windows Only)
        elif all(e in ['.docx', '.doc'] for e in exts):
            result = _convert_docx_to_pdf(valid_paths[0], pdf_path)

        # MODE 4: HTML FILES
        elif all(e in ['.html', '.htm'] for e in exts):
            result = _convert_html_to_pdf(valid_paths[0], pdf_path)

        # MODE 5: SPREADSHEETS (XLSX, CSV)
        elif all(e in ['.xlsx', '.csv', '.xls'] for e in exts):
            result = _convert_spreadsheet_to_pdf(valid_paths, pdf_path)

        else:
            supported = "Images, Text, DOCX, HTML, XLSX/CSV"
            return f"⚠️ Mixed ya unsupported file types detect hui. Ek baar mein sirf ek type select karo.\nSupported: {supported}"

        # Show file size & AUTO-OPEN
        if "SUCCESS" in result and os.path.exists(pdf_path):
            size_str = _get_file_size_str(pdf_path)
            result += f"\n📦 Output PDF size: {size_str}"
            try:
                os.startfile(target_dir)
                os.startfile(pdf_path)
            except Exception as open_err:
                logger.warning(f"Auto-open failed: {open_err}")

        return result

    except Exception as e:
        logger.error(f"PDF Conversion failed: {e}")
        return f"❌ Conversion Error ho gaya bhai: {str(e)}\nCheck karo ke file corrupt toh nahi hai aur dependencies installed hain."


def _convert_images_to_pdf(paths, output_path):
    try:
        images = []
        for path in paths:
            img = Image.open(path)
            if img.mode == "RGBA":
                img = img.convert("RGB")
            images.append(img)

        if images:
            images[0].save(output_path, save_all=True, append_images=images[1:])
            return f"✅ SUCCESS: {len(images)} image(s) se PDF ban gaya -> '{output_path}'"
        return "❌ Koi valid images nahi mili."
    except Exception as e:
        return f"❌ Image conversion error: {e}"


def _convert_text_to_pdf(paths, output_path):
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas

        c = canvas.Canvas(output_path, pagesize=letter)
        width, height = letter
        y = height - 40

        for path in paths:
            try:
                # Use `replace` (not `ignore`) so non-UTF-8 bytes become
                # visible replacement chars rather than silently vanishing —
                # users can see their file had encoding issues.
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()

                c.setFont("Helvetica-Bold", 12)
                c.drawString(40, y, f"File: {os.path.basename(path)}")
                y -= 20
                c.setFont("Courier", 10)

                for line in lines:
                    clean_line = line.strip()
                    if len(clean_line) > 90:
                        clean_line = clean_line[:90] + "..."

                    c.drawString(40, y, clean_line)
                    y -= 12
                    if y < 40:
                        c.showPage()
                        y = height - 40
                        c.setFont("Courier", 10)

                c.showPage()
                y = height - 40
            except Exception as e:
                logger.warning(f"Failed to read {path}: {e}")

        c.save()
        return f"✅ SUCCESS: {len(paths)} text file(s) se PDF ban gaya -> '{output_path}'"

    except ImportError:
        return "❌ Error: 'reportlab' library missing hai. Install karo: pip install reportlab"
    except Exception as e:
        return f"❌ Text conversion error: {e}"


def _convert_docx_to_pdf(docx_path, output_path):
    try:
        import win32com.client
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False

        doc = word.Documents.Open(docx_path)
        doc.SaveAs(output_path, FileFormat=17)
        doc.Close()
        word.Quit()
        return f"✅ SUCCESS: Document se PDF ban gaya -> '{output_path}'"
    except ImportError:
        return "❌ DOCX conversion ke liye 'pywin32' chahiye. Install karo: pip install pywin32"
    except Exception as e:
        return f"❌ DOCX conversion error (Ensure MS Word installed hai): {e}"


def _convert_html_to_pdf(html_path, output_path):
    """Converts HTML to PDF using pdfkit (wkhtmltopdf), weasyprint, or browser fallback."""
    # Attempt 1: pdfkit
    try:
        import pdfkit
        pdfkit.from_file(html_path, output_path)
        return f"✅ SUCCESS: HTML se PDF ban gaya (pdfkit) -> '{output_path}'"
    except ImportError:
        logger.info("pdfkit not available, trying weasyprint...")
    except Exception as e:
        logger.warning(f"pdfkit failed: {e}")

    # Attempt 2: weasyprint
    try:
        from weasyprint import HTML
        HTML(filename=html_path).write_pdf(output_path)
        return f"✅ SUCCESS: HTML se PDF ban gaya (weasyprint) -> '{output_path}'"
    except ImportError:
        logger.info("weasyprint not available, trying browser fallback...")
    except Exception as e:
        logger.warning(f"weasyprint failed: {e}")

    # Attempt 3: Browser fallback (Windows - open and let user print)
    try:
        import subprocess
        abs_path = os.path.abspath(html_path)
        # Try Edge's headless PDF print
        edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
        if not os.path.exists(edge_path):
            edge_path = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"

        if os.path.exists(edge_path):
            subprocess.run([
                edge_path,
                "--headless",
                "--disable-gpu",
                f"--print-to-pdf={output_path}",
                f"file:///{abs_path.replace(os.sep, '/')}"
            ], timeout=30, capture_output=True)
            if os.path.exists(output_path):
                return f"✅ SUCCESS: HTML se PDF ban gaya (Edge browser) -> '{output_path}'"

        return "❌ HTML to PDF ke liye pdfkit ya weasyprint install karo:\n  pip install pdfkit (+ wkhtmltopdf)\n  ya pip install weasyprint"
    except Exception as e:
        return f"❌ HTML to PDF conversion fail: {e}\nInstall karo: pip install pdfkit ya pip install weasyprint"


def _convert_spreadsheet_to_pdf(paths, output_path):
    """Converts XLSX/CSV files to PDF by rendering them as tables."""
    try:
        from reportlab.lib.pagesizes import landscape, letter
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet

        doc = SimpleDocTemplate(output_path, pagesize=landscape(letter))
        elements = []
        styles = getSampleStyleSheet()

        for path in paths:
            ext = os.path.splitext(path)[1].lower()
            data = []

            try:
                if ext == '.csv':
                    import csv
                    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                        reader = csv.reader(f)
                        for row in reader:
                            data.append(row)
                elif ext in ['.xlsx', '.xls']:
                    try:
                        import openpyxl
                        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
                        ws = wb.active
                        for row in ws.iter_rows(values_only=True):
                            data.append([str(cell) if cell is not None else "" for cell in row])
                        wb.close()
                    except ImportError:
                        return "❌ XLSX ke liye 'openpyxl' chahiye. Install karo: pip install openpyxl"
            except Exception as read_err:
                logger.warning(f"Failed to read {path}: {read_err}")
                continue

            if not data:
                continue

            # Add file title
            elements.append(Paragraph(f"<b>File: {os.path.basename(path)}</b>", styles['Heading2']))
            elements.append(Spacer(1, 12))

            # Limit columns/rows for readability
            max_cols = 15
            max_rows = 500
            if len(data) > max_rows:
                data = data[:max_rows]
                data.append(["... (truncated)"] + [""] * (min(len(data[0]), max_cols) - 1))
            data = [row[:max_cols] for row in data]

            # Build table
            table = Table(data, repeatRows=1)
            style_cmds = [
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4472C4')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 7),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#D9E2F3')]),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ]
            table.setStyle(TableStyle(style_cmds))
            elements.append(table)
            elements.append(Spacer(1, 24))

        if not elements:
            return "❌ Spreadsheet files se koi data nahi mila."

        doc.build(elements)
        return f"✅ SUCCESS: {len(paths)} spreadsheet(s) se PDF ban gaya -> '{output_path}'"

    except ImportError:
        return "❌ Spreadsheet to PDF ke liye 'reportlab' chahiye. Install karo: pip install reportlab"
    except Exception as e:
        return f"❌ Spreadsheet to PDF conversion error: {e}"


# ═══════════════════════════════════════════════════════════════
#  TOOL 2: GET SELECTED TEXT (existing - unchanged)
# ═══════════════════════════════════════════════════════════════

@function_tool
async def get_selected_text() -> str:
    """
    Copies the currently selected text and returns it.
    (Requires user to have text highlighted).
    """
    try:
        import pyautogui
        import pyperclip
        import asyncio

        original = pyperclip.paste()
        pyautogui.hotkey('ctrl', 'c')
        await asyncio.sleep(0.5)
        selected = pyperclip.paste()

        if not selected or selected == original:
             return "❌ Error: Mujhe koi selected text nahi mila."

        return f"--- SELECTED TEXT ---\n{selected}"
    except Exception as e:
        return f"❌ Error: {str(e)}"


# ═══════════════════════════════════════════════════════════════
#  TOOL 3: IMAGE FORMAT CONVERTER (NEW)
# ═══════════════════════════════════════════════════════════════

@function_tool
async def convert_image_format_tool(input_path: str, output_format: str = "png") -> str:
    """
    Image format converter - ek image ko dusre format mein convert karta hai.
    Supported formats: jpg, png, bmp, webp, gif, ico, tiff.
    Args:
        input_path: Source image ka full path.
        output_format: Target format (e.g., "png", "jpg", "webp", "bmp", "gif", "ico", "tiff").
    """
    try:
        SUPPORTED = ['jpg', 'jpeg', 'png', 'bmp', 'webp', 'gif', 'ico', 'tiff']
        output_format = output_format.lower().strip().replace('.', '')

        if output_format not in SUPPORTED:
            return f"❌ Unsupported format '{output_format}'. Supported: {', '.join(SUPPORTED)}"

        if not os.path.exists(input_path):
            return f"❌ File nahi mili: '{input_path}'\nCheck karo path sahi hai."

        img = Image.open(input_path)
        base_name = os.path.splitext(input_path)[0]
        src_ext = os.path.splitext(input_path)[1].lower()

        # Map format names to proper extensions
        ext_map = {'jpg': 'jpeg', 'jpeg': 'jpeg'}
        save_format = ext_map.get(output_format, output_format).upper()
        file_ext = 'jpg' if output_format in ['jpg', 'jpeg'] else output_format

        output_path = f"{base_name}.{file_ext}"

        # Avoid overwriting same file
        if os.path.abspath(output_path) == os.path.abspath(input_path):
            output_path = f"{base_name}_converted.{file_ext}"

        # Handle RGBA -> RGB for formats that don't support alpha
        if img.mode == 'RGBA' and save_format in ['JPEG', 'BMP', 'ICO']:
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])
            img = background
        elif img.mode == 'P' and save_format == 'JPEG':
            img = img.convert('RGB')
        elif img.mode not in ['RGB', 'RGBA', 'L'] and save_format == 'JPEG':
            img = img.convert('RGB')

        # Special handling for ICO
        if save_format == 'ICO':
            sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
            img.save(output_path, format='ICO', sizes=sizes)
        else:
            img.save(output_path, format=save_format)

        src_size = _get_file_size_str(input_path)
        out_size = _get_file_size_str(output_path)

        return (
            f"✅ SUCCESS: Image convert ho gayi!\n"
            f"📁 Source: {os.path.basename(input_path)} ({src_ext}) -> {file_ext.upper()}\n"
            f"📦 {src_size} -> {out_size}\n"
            f"💾 Saved: '{output_path}'"
        )

    except Exception as e:
        logger.error(f"Image format conversion failed: {e}")
        return f"❌ Image conversion error: {str(e)}\nCheck karo ke file ek valid image hai."


# ═══════════════════════════════════════════════════════════════
#  TOOL 4: IMAGE RESIZER (NEW)
# ═══════════════════════════════════════════════════════════════

@function_tool
async def resize_image_tool(input_path: str, width: int = 0, height: int = 0, scale_percent: int = 0) -> str:
    """
    Image resizer - image ka size change karta hai.
    Width/Height doge toh exact resize hoga, ya scale_percent doge toh percentage se resize hoga.
    Agar sirf width ya height doge, aspect ratio maintain hoga.
    Args:
        input_path: Image ka full path.
        width: Naya width in pixels (0 = auto-calculate from height).
        height: Nayi height in pixels (0 = auto-calculate from width).
        scale_percent: Percentage se resize (e.g., 50 = aadha size, 200 = double).
    """
    try:
        if not os.path.exists(input_path):
            return f"❌ File nahi mili: '{input_path}'"

        img = Image.open(input_path)
        orig_w, orig_h = img.size

        if scale_percent > 0:
            new_w = int(orig_w * scale_percent / 100)
            new_h = int(orig_h * scale_percent / 100)
            mode_desc = f"Scale {scale_percent}%"
        elif width > 0 and height > 0:
            new_w = width
            new_h = height
            mode_desc = f"Exact {new_w}x{new_h}"
        elif width > 0:
            ratio = width / orig_w
            new_w = width
            new_h = int(orig_h * ratio)
            mode_desc = f"Width={new_w}, aspect ratio maintained"
        elif height > 0:
            ratio = height / orig_h
            new_w = int(orig_w * ratio)
            new_h = height
            mode_desc = f"Height={new_h}, aspect ratio maintained"
        else:
            return "⚠️ Resize ke liye width/height ya scale_percent dena zaroori hai!\nExample: width=800 ya scale_percent=50"

        if new_w <= 0 or new_h <= 0:
            return "❌ Invalid dimensions - width aur height positive honi chahiye."

        resized = img.resize((new_w, new_h), Image.LANCZOS)

        # Save with _resized suffix
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}_resized{ext}"

        # Handle format for saving
        if img.mode == 'RGBA' and ext.lower() in ['.jpg', '.jpeg']:
            resized = resized.convert('RGB')

        resized.save(output_path)

        src_size = _get_file_size_str(input_path)
        out_size = _get_file_size_str(output_path)

        return (
            f"✅ SUCCESS: Image resize ho gayi!\n"
            f"📐 Original: {orig_w}x{orig_h} ({src_size})\n"
            f"📐 New: {new_w}x{new_h} ({out_size})\n"
            f"🔧 Mode: {mode_desc}\n"
            f"💾 Saved: '{output_path}'"
        )

    except Exception as e:
        logger.error(f"Image resize failed: {e}")
        return f"❌ Resize error: {str(e)}"


# ═══════════════════════════════════════════════════════════════
#  TOOL 5: IMAGE COMPRESSOR (NEW)
# ═══════════════════════════════════════════════════════════════

@function_tool
async def compress_image_tool(input_path: str, quality: int = 70) -> str:
    """
    Image compressor - image ka file size reduce karta hai quality adjust karke.
    PNG ko JPEG mein convert karke compress karta hai.
    Args:
        input_path: Image ka full path.
        quality: Compression quality 1-100 (kam = zyada compression, 70 recommended).
    """
    try:
        if not os.path.exists(input_path):
            return f"❌ File nahi mili: '{input_path}'"

        if quality < 1 or quality > 100:
            return "⚠️ Quality 1 se 100 ke beech honi chahiye. (70 recommended hai)"

        img = Image.open(input_path)
        orig_size = os.path.getsize(input_path)
        base, ext = os.path.splitext(input_path)
        ext_lower = ext.lower()

        # For PNG, convert to JPEG for actual compression
        if ext_lower == '.png':
            output_path = f"{base}_compressed.jpg"
            if img.mode == 'RGBA':
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[3])
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            img.save(output_path, format='JPEG', quality=quality, optimize=True)
            format_note = "(PNG -> JPEG convert hua for compression)"
        elif ext_lower in ['.jpg', '.jpeg']:
            output_path = f"{base}_compressed{ext}"
            if img.mode != 'RGB':
                img = img.convert('RGB')
            img.save(output_path, format='JPEG', quality=quality, optimize=True)
            format_note = ""
        elif ext_lower == '.webp':
            output_path = f"{base}_compressed.webp"
            img.save(output_path, format='WEBP', quality=quality, optimize=True)
            format_note = ""
        else:
            # Generic: convert to JPEG
            output_path = f"{base}_compressed.jpg"
            if img.mode in ['RGBA', 'P']:
                img = img.convert('RGB')
            img.save(output_path, format='JPEG', quality=quality, optimize=True)
            format_note = f"({ext} -> JPEG convert hua for compression)"

        new_size = os.path.getsize(output_path)
        reduction = ((orig_size - new_size) / orig_size) * 100 if orig_size > 0 else 0

        orig_str = _get_file_size_str(input_path)
        new_str = _get_file_size_str(output_path)

        status = "🟢 Acchi compression!" if reduction > 10 else "🟡 File pehle se kaafi optimized thi"

        return (
            f"✅ SUCCESS: Image compress ho gayi!\n"
            f"📦 Before: {orig_str}\n"
            f"📦 After: {new_str}\n"
            f"📉 Reduction: {reduction:.1f}% {status}\n"
            f"🔧 Quality: {quality}/100 {format_note}\n"
            f"💾 Saved: '{output_path}'"
        )

    except Exception as e:
        logger.error(f"Image compression failed: {e}")
        return f"❌ Compression error: {str(e)}"


# ═══════════════════════════════════════════════════════════════
#  TOOL 6: PDF MERGER (NEW)
# ═══════════════════════════════════════════════════════════════

@function_tool
async def merge_pdfs_tool(pdf_paths: str, output_name: str = "merged") -> str:
    """
    Multiple PDF files ko ek single PDF mein merge karta hai.
    Args:
        pdf_paths: Comma-separated PDF file paths (e.g., "C:/a.pdf, C:/b.pdf, C:/c.pdf").
        output_name: Output PDF ka naam (without .pdf extension).
    """
    try:
        # Parse comma-separated paths
        paths = [p.strip().strip('"').strip("'") for p in pdf_paths.split(',')]
        paths = [p for p in paths if p]

        if len(paths) < 2:
            return "⚠️ Merge ke liye kam se kam 2 PDF files chahiye!\nComma se separate karke paths do: \"file1.pdf, file2.pdf\""

        # Validate all files exist and are PDFs
        valid = []
        for p in paths:
            if not os.path.exists(p):
                return f"❌ File nahi mili: '{p}'"
            if not p.lower().endswith('.pdf'):
                return f"❌ Ye PDF nahi hai: '{p}'\nSirf .pdf files dena."
            valid.append(p)

        # Output path
        home = os.path.expanduser("~")
        target_dir = os.path.join(home, "Documents", "Shell_PDFs")
        os.makedirs(target_dir, exist_ok=True)
        output_path = os.path.join(target_dir, f"{output_name}.pdf")

        # Try PyPDF2 first, then pikepdf
        merged = False

        # Attempt 1: PyPDF2
        try:
            from PyPDF2 import PdfMerger
            merger = PdfMerger()
            total_pages = 0
            for p in valid:
                merger.append(p)
                from PyPDF2 import PdfReader
                reader = PdfReader(p)
                total_pages += len(reader.pages)
            merger.write(output_path)
            merger.close()
            merged = True
        except ImportError:
            logger.info("PyPDF2 not available, trying pikepdf...")
        except Exception as e:
            logger.warning(f"PyPDF2 merge failed: {e}")

        # Attempt 2: pikepdf
        if not merged:
            try:
                import pikepdf
                pdf_out = pikepdf.Pdf.new()
                total_pages = 0
                for p in valid:
                    src = pikepdf.open(p)
                    pdf_out.pages.extend(src.pages)
                    total_pages += len(src.pages)
                pdf_out.save(output_path)
                pdf_out.close()
                merged = True
            except ImportError:
                return "❌ PDF merge ke liye PyPDF2 ya pikepdf chahiye.\nInstall karo: pip install PyPDF2  ya  pip install pikepdf"
            except Exception as e:
                return f"❌ pikepdf merge error: {e}"

        if not merged:
            return "❌ PDF merge fail ho gaya. Check karo ke PDF files corrupt toh nahi."

        out_size = _get_file_size_str(output_path)

        # Auto-open
        try:
            os.startfile(output_path)
        except Exception as _e:
            logger.debug("ignored Exception: %s", _e)

        return (
            f"✅ SUCCESS: {len(valid)} PDFs merge ho gayi!\n"
            f"📄 Total pages: {total_pages}\n"
            f"📦 Output size: {out_size}\n"
            f"💾 Saved: '{output_path}'"
        )

    except Exception as e:
        logger.error(f"PDF merge failed: {e}")
        return f"❌ PDF Merge error: {str(e)}"
