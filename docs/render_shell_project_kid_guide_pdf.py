from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QMarginsF, QUrl
from PyQt6.QtGui import QPageLayout, QPageSize, QTextDocument
from PyQt6.QtPrintSupport import QPrinter
from PyQt6.QtWidgets import QApplication


ROOT = Path(__file__).resolve().parent
HTML_PATH = ROOT / "shell_project_kid_guide.html"
PDF_PATH = ROOT / "Shell_AI_Project_Kid_Friendly_Guide_Hinglish.pdf"


def render_pdf() -> None:
    app = QApplication.instance() or QApplication([])

    html = HTML_PATH.read_text(encoding="utf-8")
    document = QTextDocument()
    document.setBaseUrl(QUrl.fromLocalFile(str(ROOT) + "/"))
    document.setHtml(html)

    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(str(PDF_PATH))
    printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    printer.setPageMargins(QMarginsF(12, 12, 12, 14), QPageLayout.Unit.Millimeter)

    page_rect = printer.pageRect(QPrinter.Unit.Point)
    document.setPageSize(page_rect.size())
    document.print(printer)

    app.processEvents()


if __name__ == "__main__":
    render_pdf()
    print(PDF_PATH)
