import os, sys, traceback, faulthandler
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['OMP_NUM_THREADS'] = '1'

# QtWebEngine / Chromium switches — MUST be set before QtWebEngine is
# imported. Windows Server (and any GPU-less RDP host) blocklists WebGL
# by default; SwiftShader gives us a software GL implementation that's
# slow but correct, which is what the Three.js orb on the voice page
# needs to render anything at all. `ignore-gpu-blocklist` lets the
# blocklisted GPU still attempt hardware paths — fast machines win.
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

faulthandler.enable()


def _brand_icon_path():
    root = os.path.dirname(os.path.abspath(__file__))
    for rel in (
        os.path.join("shell_web_ui", "dist", "shell-logo.png"),
        os.path.join("shell_web_ui", "src", "public", "shell-logo.png"),
        os.path.join("shell_ui", "shell_logo.png"),
        os.path.join("assets", "brand", "shell-official-logo.png"),
    ):
        candidate = os.path.join(root, rel)
        if os.path.exists(candidate):
            return candidate
    return ""

try:
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'shell_ui'))
    print("Importing...", flush=True)

    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtGui import QPalette, QColor, QIcon

    # QtWebEngine (used by the voice-page Three.js orb) requires
    # AA_ShareOpenGLContexts to be set BEFORE QApplication is created,
    # AND its widget module to be imported beforehand so the global
    # WebEngine bootstrap runs. Without this the orb falls back to the
    # legacy painted visualizer.
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)
    try:
        from PyQt6 import QtWebEngineWidgets, QtWebEngineCore  # noqa: F401
    except Exception as _we_err:
        print(f"QtWebEngine pre-import failed (non-fatal): {_we_err}", flush=True)

    # Load .env before importing ShellHoloUI. shell_cinematic_full initializes
    # MultiAIBrain at module import time, so provider keys must already be in
    # os.environ or the UI falls back even when .env is configured.
    try:
        from shell_config import config as _shell_config  # noqa: F401
    except Exception as _cfg_err:
        print(f"Config load failed (non-fatal): {_cfg_err}", flush=True)

    use_legacy_ui = os.environ.get("SHELL_LEGACY_UI", "0").strip().lower() in {"1", "true", "yes", "on"}
    if use_legacy_ui:
        from shell_cinematic_full import ShellHoloUI
    else:
        from shell_web_ui.host import ShellWebUI
    print("Imports OK", flush=True)

    app = QApplication(sys.argv)
    _brand_icon = _brand_icon_path()
    if _brand_icon:
        app.setWindowIcon(QIcon(_brand_icon))
    app.setStyle("Fusion")
    try:
        from shell_ui.app_bootstrap import configure_qt_application

        configure_qt_application(app)
    except Exception as _font_err:
        print(f"Font bootstrap failed (non-fatal): {_font_err}", flush=True)
    dp = QPalette()
    _dark = QColor(4, 7, 16); _darker = QColor(2, 3, 10)
    dp.setColor(QPalette.ColorRole.Window, _dark)
    dp.setColor(QPalette.ColorRole.WindowText, QColor(200, 210, 220))
    dp.setColor(QPalette.ColorRole.Base, _darker)
    dp.setColor(QPalette.ColorRole.Text, QColor(200, 210, 220))
    dp.setColor(QPalette.ColorRole.Button, _dark)
    dp.setColor(QPalette.ColorRole.ButtonText, QColor(200, 210, 220))
    app.setPalette(dp)

    sys.excepthook = lambda *a: print(f"UNCAUGHT: {''.join(traceback.format_exception(*a))}", flush=True)

    # ---- Boot splash ----------------------------------------------------
    # ShellHoloUI() can take 3-5s on cold start. Show a Mac-style splash
    # immediately so the user sees branded feedback instead of a blank
    # screen. Wrapped in try/except so a broken splash never blocks boot.
    splash = None
    try:
        from shell_ui.splash_screen import SplashScreen
        splash = SplashScreen(total_duration_ms=3000)
        splash.show()
        # Pump events so the splash actually paints before the heavy
        # ShellHoloUI constructor below blocks the event loop.
        app.processEvents()
    except Exception as _splash_err:
        print(f"Splash failed (non-fatal): {_splash_err}", flush=True)
        splash = None

    print("Creating UI...", flush=True)
    w = ShellHoloUI() if use_legacy_ui else ShellWebUI()
    if _brand_icon:
        w.setWindowIcon(QIcon(_brand_icon))
    # Fit inside the visible desktop work area. This prevents the macOS Dock
    # or Windows taskbar from covering the bottom action rows.
    try:
        geo = app.primaryScreen().availableGeometry()
        w.resize(min(1280, max(960, geo.width() - 40)),
                 min(720, max(620, geo.height() - 60)))
        w.move(geo.x() + max(20, (geo.width() - w.width()) // 2),
               geo.y() + max(20, (geo.height() - w.height()) // 2))
    except Exception:
        w.resize(1180, 640)
    w.show()
    ui_name = "legacy PyQt UI" if use_legacy_ui else "Shell AI Web UI"
    print(f"Shell OS 1.0.0 is live with {ui_name}. Window open. Created by mdshoebking.", flush=True)

    # Once the main window is up, fade the splash out smoothly.
    if splash is not None:
        try:
            splash.dismiss()
        except Exception as _splash_dismiss_err:
            print(f"Splash dismiss failed (non-fatal): {_splash_dismiss_err}", flush=True)

    app.exec()
    print("App closed normally.", flush=True)
except Exception as e:
    print(f"FATAL: {e}", flush=True)
    print(traceback.format_exc(), flush=True)
    if sys.stdout.isatty():
        input("Press Enter to exit...")
