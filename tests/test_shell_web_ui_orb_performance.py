from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_project_file(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_sphere_matches_original_voice_reactive_orb():
    sphere = read_project_file("shell_web_ui/src/components/Sphere.tsx")

    assert "const CustomParticleSphere = ({" in sphere
    assert "count = 2000" in sphere
    assert "voiceLevel = 0" in sphere
    assert "speaking = false" in sphere
    assert "const ORB_AUDIO_COLOR = '#33db12'" in sphere
    assert "const ORB_PEAK_COLOR = '#FFFFFF'" in sphere
    assert "const ORB_BASE_COLOR = '#00F0FF'" in sphere
    assert "shellService.analyser.getByteFrequencyData" in sphere
    assert "liveVolume = sum / len / 128" in sphere
    assert "const backendLevel = Math.min(1, Math.max(0, voiceLevel || 0))" in sphere
    assert "const speechPulse = speaking ?" in sphere


def test_sphere_preserves_original_particle_expansion_on_gpu():
    sphere = read_project_file("shell_web_ui/src/components/Sphere.tsx")

    assert "spreadFactors" in sphere
    assert "attribute float spreadFactor" in sphere
    assert "const ORB_EXPANSION_STRENGTH = 0.4" in sphere
    assert "position * (1.0 + uVolume * spreadFactor * uExpansionStrength)" in sphere
    assert "geometry.attributes.position.needsUpdate = true" not in sphere
    assert "currentPos[ix]" not in sphere
    assert "originalPositions" not in sphere


def test_sphere_uses_windows_friendly_canvas_runtime_settings():
    sphere = read_project_file("shell_web_ui/src/components/Sphere.tsx")

    assert "const ORB_TARGET_FRAME_MS = 1000 / 30" in sphere
    assert "dpr={[1, 1.2]}" in sphere
    assert "performance={{ min: 0.5 }}" in sphere
    assert "powerPreference: 'default'" in sphere
    assert "if (document.hidden) return" in sphere
    assert "const ORB_PARTICLE_SIZE = 0.012" in sphere
    assert "shaderMaterial" in sphere
    assert "uScale" in sphere
    assert "uSize" in sphere


def test_dashboard_uses_original_orb_wrapper():
    dashboard = read_project_file("shell_web_ui/src/views/Dashboard.tsx")

    assert "w-[60vh] h-[60vh] max-w-full transition-opacity duration-300" in dashboard
    assert "opacity-92 scale-95" in dashboard
    assert "grayscale" not in dashboard
    assert "shell-sphere-shell" not in dashboard


def test_sphere_uses_desktop_style_css_orb_for_packaged_windows():
    sphere = read_project_file("shell_web_ui/src/components/Sphere.tsx")
    css = read_project_file("shell_web_ui/src/assets/main.css")
    main = read_project_file("shell_web_ui/src/main.tsx")
    host = read_project_file("shell_web_ui/host.py")

    assert "shell-windows-perf" in main
    assert "shell_perf=windows" in host
    assert "const cssOnlyOrb" in sphere
    assert "!cssOnlyOrb &&" in sphere
    assert "shell-orb-blob shell-orb-blob-one" in sphere
    assert "shell-orb-wisp shell-orb-wisp-one" in sphere
    assert ".shell-orb-core" in css
    assert ".shell-orb-ring" in css
    assert ".shell-windows-perf .shell-liquid-panel" in css


def test_dashboard_throttles_face_scan_on_windows_or_low_core_devices():
    dashboard = read_project_file("shell_web_ui/src/views/Dashboard.tsx")

    assert "WINDOWS_OR_LOW_CORE_DEVICE" in dashboard
    assert "/Windows/i.test(navigator.userAgent || '')" in dashboard
    assert "FACE_SCAN_INTERVAL_MS = WINDOWS_OR_LOW_CORE_DEVICE ? 500 : 250" in dashboard
    assert "}, FACE_SCAN_INTERVAL_MS)" in dashboard


def test_shell_ai_uses_adaptive_history_polling_for_windows_smoothness():
    shell_ai = read_project_file("shell_web_ui/src/UI/ShellAI.tsx")

    assert "const PRELOAD_TAB_GAP_MS = 180" in shell_ai
    assert "new URLSearchParams(window.location.search).get('shell_perf')" in shell_ai
    assert "if (shellPerfMode === 'windows') return true" in shell_ai
    assert "HISTORY_ACTIVE_POLL_MS = 900" in shell_ai
    assert "HISTORY_IDLE_POLL_MS = 2500" in shell_ai
    assert "HISTORY_BACKGROUND_POLL_MS = 6000" in shell_ai
    assert "document.hidden" in shell_ai
    assert "setInterval(fetchHistory, 500)" not in shell_ai
