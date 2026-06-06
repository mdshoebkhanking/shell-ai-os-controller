from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def read_project_file(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_shell_tab_pane_stays_mounted_and_avoids_surface_animation():
    shell_ai = read_project_file("shell_web_ui/src/UI/ShellAI.tsx")
    css = read_project_file("shell_web_ui/src/assets/main.css")

    assert "key={activeTab}" not in shell_ai
    assert "useTransition" in shell_ai
    assert "startTabTransition" in shell_ai
    assert "selectShellTab(tab.id)" in shell_ai
    assert "setActiveTab(tabId)" in shell_ai
    assert "shell-view-layer" in shell_ai

    pane_match = re.search(r"\.shell-view-pane\s*\{(?P<body>.*?)\n\}", css, flags=re.DOTALL)
    assert pane_match is not None
    pane_body = pane_match.group("body")

    assert "animation:" not in pane_body
    assert "will-change" not in pane_body
    assert "display: flex" in pane_body
    assert "overflow: hidden" in pane_body
    assert "isolation: isolate" in pane_body

    layer_match = re.search(r"\.shell-view-layer\s*\{(?P<body>.*?)\n\}", css, flags=re.DOTALL)
    assert layer_match is not None
    layer_body = layer_match.group("body")
    assert "display: flex" in layer_body
    assert "flex-direction: column" in layer_body
    assert "position: relative" in layer_body
    assert "width: 100%" in layer_body
    assert "height: 100%" in layer_body
    assert "min-height: 0" in layer_body
    assert "overflow: hidden" in layer_body

    layer_child_match = re.search(
        r"\.shell-view-layer\s*>\s*\*\s*\{(?P<body>.*?)\n\}", css, flags=re.DOTALL
    )
    assert layer_child_match is not None
    layer_child_body = layer_child_match.group("body")
    assert "flex: 1 1 auto" in layer_child_body
    assert "width: 100%" in layer_child_body
    assert "max-width: 100%" in layer_child_body
    assert "min-height: 0" in layer_child_body


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
        assert "animate-in fade-in duration-150" not in content


def test_lazy_tab_views_can_preload_before_first_switch_when_enabled():
    shell_ai = read_project_file("shell_web_ui/src/UI/ShellAI.tsx")
    skeleton = read_project_file("shell_web_ui/src/components/ViewSkelrton.tsx")

    for loader in [
        "loadAppsView",
        "loadWorkFlowEditorView",
        "loadNotesView",
        "loadSettingsView",
        "loadGalleryView",
        "loadControlCenterView",
        "loadPhoneView",
    ]:
        assert f"const {loader}" in shell_ai
        assert loader in shell_ai

    assert "const preloadShellTabViews" in shell_ai
    assert "const shouldPreloadShellTabs" in shell_ai
    assert "Windows" in shell_ai
    assert "shell_preload_tabs" in shell_ai
    assert "void preloadShellTabViews(() => cancelled).catch(() => undefined)" in shell_ai
    assert "requestIdleCallback" in shell_ai
    assert "animate-in" not in skeleton
    assert "fade-in" not in skeleton


def test_lazy_tab_preload_is_staggered_to_avoid_startup_jank():
    shell_ai = read_project_file("shell_web_ui/src/UI/ShellAI.tsx")

    assert "const shellTabViewLoaders = [" in shell_ai
    assert "const PRELOAD_TAB_GAP_MS = 120" in shell_ai
    assert "await waitForPreloadGap()" in shell_ai
    assert "for (const loadView of shellTabViewLoaders)" in shell_ai
    assert "await loadView()" in shell_ai
    assert "Promise.all([" not in shell_ai
    assert "let cancelled = false" in shell_ai
    assert "cancelled = true" in shell_ai


def test_shell_root_avoids_idle_render_churn():
    shell_ai = read_project_file("shell_web_ui/src/UI/ShellAI.tsx")
    dashboard = read_project_file("shell_web_ui/src/views/Dashboard.tsx")

    assert "getSystemStatus" not in shell_ai
    assert "setStats" not in shell_ai
    assert "historyRequestInFlightRef" in shell_ai
    assert "lastHistorySignatureRef" in shell_ai
    assert "nextSignature === lastHistorySignatureRef.current" in shell_ai
    assert "current.transform === nextStyle.transform" in shell_ai
    assert "current.width === nextStyle.width" in shell_ai
    assert "export default memo(" in dashboard
    assert "areDashboardShellPropsEqual" in dashboard


def test_heavy_widgets_defer_map_editor_and_terminal_libraries_until_visible():
    map_view = read_project_file("shell_web_ui/src/Widgets/MapView.tsx")
    map_canvas = read_project_file("shell_web_ui/src/Widgets/MapCanvas.tsx")
    live_coding = read_project_file("shell_web_ui/src/Widgets/LiveCodingWidget.tsx")
    live_editor = read_project_file("shell_web_ui/src/Widgets/LiveCodingEditor.tsx")
    terminal = read_project_file("shell_web_ui/src/components/TerminalOverlay.tsx")

    assert "lazy(() => import('./MapCanvas'))" in map_view
    assert "from 'react-leaflet'" not in map_view
    assert "from 'leaflet'" not in map_view
    assert "from 'react-leaflet'" in map_canvas
    assert "from 'leaflet'" in map_canvas

    assert "lazy(() => import('./LiveCodingEditor'))" in live_coding
    assert "from '@monaco-editor/react'" not in live_coding
    assert "from '@monaco-editor/react'" in live_editor

    assert "from 'xterm'" not in terminal
    assert "from 'xterm-addon-fit'" not in terminal
    assert "import('xterm')" in terminal
    assert "import('xterm-addon-fit')" in terminal


def test_macro_runner_reports_failures_inline_without_browser_alerts():
    workflow_editor = read_project_file("shell_web_ui/src/views/WorkFlowEditor.tsx")

    assert "alert(" not in workflow_editor
    assert "role=\"status\"" in workflow_editor
    assert "aria-live=\"polite\"" in workflow_editor
    assert "Execution failed:" in workflow_editor
    assert "Macro execution halted at" in workflow_editor
