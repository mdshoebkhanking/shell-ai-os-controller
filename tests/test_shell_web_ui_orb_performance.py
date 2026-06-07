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
    assert "const ORB_BASE_COLOR = '#7ED3BA'" in sphere
    assert "const ORB_AUDIO_COLOR = '#5EEAD4'" in sphere
    assert "const ORB_PEAK_COLOR = '#ECFDF5'" in sphere
    assert "shellService.analyser.getByteFrequencyData" in sphere
    assert "liveVolume = sum / len / 128" in sphere
    assert "const backendLevel = Math.min(1, Math.max(0, voiceLevel || 0))" in sphere
    assert "const speechPulse = speaking ?" in sphere
    assert "colorTarget.lerpColors(colorStart, colorMid" in sphere
    assert "colorTarget.lerpColors(colorMid, colorEnd" in sphere


def test_sphere_preserves_original_particle_expansion_on_gpu():
    sphere = read_project_file("shell_web_ui/src/components/Sphere.tsx")

    assert "spreadFactors" in sphere
    assert "attribute float spreadFactor" in sphere
    assert "const ORB_EXPANSION_STRENGTH = 0.4" in sphere
    assert "const ORB_PARTICLE_RADIUS = 1.93" in sphere
    assert "position * (1.0 + uVolume * spreadFactor * uExpansionStrength)" in sphere
    assert "vector.normalize().multiplyScalar(ORB_PARTICLE_RADIUS)" in sphere
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
    assert "const ORB_PARTICLE_SIZE = 0.011" in sphere
    assert "const ORB_ROTATION_Y_SPEED = 0.14" in sphere
    assert "mesh.current.rotation.y += delta * ORB_ROTATION_Y_SPEED" in sphere
    assert "shaderMaterial" in sphere
    assert "uScale" in sphere
    assert "uSize" in sphere


def test_dashboard_uses_original_orb_wrapper():
    dashboard = read_project_file("shell_web_ui/src/views/Dashboard.tsx")

    assert "w-[60vh] h-[60vh] max-w-full transition-opacity duration-300" in dashboard
    assert "opacity-92 scale-95" in dashboard
    assert "grayscale" not in dashboard
    assert "shell-sphere-shell" not in dashboard


def test_sphere_preserves_desktop_particle_orb_for_packaged_windows():
    sphere = read_project_file("shell_web_ui/src/components/Sphere.tsx")
    css = read_project_file("shell_web_ui/src/assets/main.css")
    main = read_project_file("shell_web_ui/src/main.tsx")
    host = read_project_file("shell_web_ui/host.py")

    assert "shellPerfMode !== 'windows'" in main
    assert "explicitSafePerfMode" in main
    assert "shell_perf=windows" in host
    assert "const cssOnlyOrb" not in sphere
    assert "<Canvas" in sphere
    assert "shell-orb-canvas" in sphere
    assert "shell-orb-fallback\" />" in sphere
    assert "shell-orb-blob" not in sphere
    assert "shell-orb-wisp" not in sphere
    assert ".shell-orb-fallback::before" in css
    assert "rgba(126, 211, 186" in css
    assert "rgba(94, 234, 212" in css
    assert ".shell-orb-particle-drift" not in css[css.index(".shell-orb-stage") : css.index(".shell-liquid-dock")]
    assert "rgba(0, 240, 255" not in css[css.index(".shell-orb-stage") : css.index(".shell-liquid-dock")]
    assert ".shell-windows-perf .shell-liquid-panel" in css


def test_dashboard_throttles_face_scan_on_windows_or_low_core_devices():
    dashboard = read_project_file("shell_web_ui/src/views/Dashboard.tsx")

    assert "WINDOWS_OR_LOW_CORE_DEVICE" in dashboard
    assert "/Windows/i.test(navigator.userAgent || '')" in dashboard
    assert "FACE_SCAN_INTERVAL_MS = WINDOWS_OR_LOW_CORE_DEVICE ? 900 : 250" in dashboard
    assert "VOICE_AMPLITUDE_MIN_PAINT_MS = WINDOWS_OR_LOW_CORE_DEVICE ? 48 : 32" in dashboard
    assert "VOICE_AMPLITUDE_MIN_DELTA = 0.035" in dashboard
    assert "const updateVoiceAmplitude = useCallback" in dashboard
    assert "}, FACE_SCAN_INTERVAL_MS)" in dashboard


def test_windows_perf_mode_is_explicit_safe_mode_not_default_packaged_mode():
    css = read_project_file("shell_web_ui/src/assets/main.css")
    main = read_project_file("shell_web_ui/src/main.tsx")
    perf_css = css[css.index(".shell-windows-perf .shell-ui-root") : css.index(".shell-tabs {")]

    assert "explicitSafePerfMode" in main
    assert "['safe', 'low', 'eco'].includes(shellPerfMode)" in main
    assert "shellPerfMode === 'windows' ||" not in main
    assert ".shell-windows-perf .shell-liquid-panel::before" in perf_css
    assert ".shell-windows-perf .shell-workstream-panel::after" in perf_css
    assert ".shell-windows-perf .shell-control-surface::before" in perf_css
    assert "display: none !important" in perf_css
    assert ".shell-windows-perf .shell-logo-glass img" in perf_css
    assert ".shell-windows-perf .shell-dock-button svg" in perf_css
    assert "filter: none !important" in perf_css
    assert "contain: layout paint" in perf_css
    assert "animation: none !important" in perf_css


def test_shell_ai_uses_adaptive_history_polling_for_windows_smoothness():
    shell_ai = read_project_file("shell_web_ui/src/UI/ShellAI.tsx")

    assert "const PRELOAD_TAB_GAP_MS = 180" in shell_ai
    assert "new URLSearchParams(window.location.search)" in shell_ai
    assert "if (shellPerfMode === 'windows') return false" in shell_ai
    assert "if (shellSearchParams.get('shell_host') === 'pyqt') return false" in shell_ai
    assert "HISTORY_ACTIVE_POLL_MS = 900" in shell_ai
    assert "HISTORY_IDLE_POLL_MS = 2500" in shell_ai
    assert "HISTORY_BACKGROUND_POLL_MS = 6000" in shell_ai
    assert "document.hidden" in shell_ai
    assert "setInterval(fetchHistory, 500)" not in shell_ai
