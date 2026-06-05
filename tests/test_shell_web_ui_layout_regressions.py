from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_three_column_layout_waits_until_xl_breakpoint():
    dashboard = (ROOT / "shell_web_ui" / "src" / "views" / "Dashboard.tsx").read_text(encoding="utf-8")

    assert "hidden xl:flex xl:col-span-3" in dashboard
    assert "md:col-span-7 xl:col-span-5" in dashboard
    assert "md:col-span-5 xl:col-span-4" in dashboard
    assert "hidden lg:flex col-span-3" not in dashboard
    assert "lg:col-span-5" not in dashboard
    assert "lg:col-span-4" not in dashboard


def test_dashboard_orb_listens_to_backend_voice_amplitude():
    dashboard = (ROOT / "shell_web_ui" / "src" / "views" / "Dashboard.tsx").read_text(encoding="utf-8")
    sphere = (ROOT / "shell_web_ui" / "src" / "components" / "Sphere.tsx").read_text(encoding="utf-8")

    assert "voice-amplitude" in dashboard
    assert "voiceLevel={voiceAmplitude}" in dashboard
    assert "speaking={speechState === 'SPEAKING' || speechState === 'GEMINI LIVE'}" in dashboard
    assert "backendLevel" in sphere
    assert "speechPulse" in sphere
    assert "idlePulse" in sphere


def test_primary_tabs_can_scroll_inside_tight_windows():
    shell_ai = (ROOT / "shell_web_ui" / "src" / "UI" / "ShellAI.tsx").read_text(encoding="utf-8")
    css = (ROOT / "shell_web_ui" / "src" / "assets" / "main.css").read_text(encoding="utf-8")

    assert "shell-primary-tabs" in shell_ai
    assert "flex-1 items-center justify-center" in shell_ai
    assert ".shell-primary-tabs" in css
    assert "overflow-x: auto" in css
