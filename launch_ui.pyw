"""Launch Shell OS UI — .pyw extension keeps it as a GUI process without console."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'shell_ui'))
if sys.platform.startswith("win"):
    os.environ.setdefault('QT_QPA_PLATFORM', 'windows')
os.environ.setdefault(
    "QTWEBENGINE_CHROMIUM_FLAGS",
    " ".join([
        "--ignore-gpu-blocklist",
        "--enable-webgl",
        "--enable-unsafe-swiftshader",
        "--disable-gpu-sandbox",
        "--disable-software-rasterizer-fallback-when-hardware-fails",
    ]),
)

# QApplication MUST be created before importing shell_cinematic_full
# (module-level code references Qt types that need an app instance)
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont

QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
try:
    from PyQt6 import QtWebEngineWidgets, QtWebEngineCore  # noqa: F401
except Exception:
    pass

app = QApplication(sys.argv)
app.setStyle('Fusion')

from shell_cinematic_full import ShellHoloUI, _FONT

app_font = QFont(_FONT)
app_font.setPixelSize(13)
app_font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
app.setFont(app_font)

w = ShellHoloUI()
w.show()
w.raise_()
w.activateWindow()
app.exec()
