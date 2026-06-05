from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def read_project_file(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_shell_tab_pane_stays_mounted_and_avoids_surface_animation():
    shell_ai = read_project_file("shell_web_ui/src/UI/ShellAI.tsx")
    css = read_project_file("shell_web_ui/src/assets/main.css")

    assert "key={activeTab}" not in shell_ai

    pane_match = re.search(r"\.shell-view-pane\s*\{(?P<body>.*?)\n\}", css, flags=re.DOTALL)
    assert pane_match is not None
    pane_body = pane_match.group("body")

    assert "animation:" not in pane_body
    assert "will-change" not in pane_body
    assert "overflow: hidden" in pane_body
    assert "isolation: isolate" in pane_body


def test_primary_tab_views_do_not_zoom_during_tab_switches():
    primary_views = [
        "shell_web_ui/src/views/Dashboard.tsx",
        "shell_web_ui/src/views/ControlCenter.tsx",
        "shell_web_ui/src/views/APP.tsx",
        "shell_web_ui/src/views/Notes.tsx",
        "shell_web_ui/src/views/Gallery.tsx",
    ]

    for relative_path in primary_views:
        content = read_project_file(relative_path)
        assert "animate-in fade-in zoom-in" not in content
