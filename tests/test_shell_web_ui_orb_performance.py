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

    assert "w-[60vh] h-[60vh] max-w-full transition-all duration-1000" in dashboard
    assert "opacity-85 scale-90 grayscale" in dashboard
    assert "shell-sphere-shell" not in dashboard


def test_dashboard_throttles_face_scan_on_windows_or_low_core_devices():
    dashboard = read_project_file("shell_web_ui/src/views/Dashboard.tsx")

    assert "WINDOWS_OR_LOW_CORE_DEVICE" in dashboard
    assert "/Windows/i.test(navigator.userAgent || '')" in dashboard
    assert "FACE_SCAN_INTERVAL_MS = WINDOWS_OR_LOW_CORE_DEVICE ? 500 : 250" in dashboard
    assert "}, FACE_SCAN_INTERVAL_MS)" in dashboard


def test_shell_ai_uses_adaptive_history_polling_for_windows_smoothness():
    shell_ai = read_project_file("shell_web_ui/src/UI/ShellAI.tsx")

    assert "HISTORY_ACTIVE_POLL_MS = 900" in shell_ai
    assert "HISTORY_IDLE_POLL_MS = 2500" in shell_ai
    assert "HISTORY_BACKGROUND_POLL_MS = 6000" in shell_ai
    assert "document.hidden" in shell_ai
    assert "setInterval(fetchHistory, 500)" not in shell_ai
