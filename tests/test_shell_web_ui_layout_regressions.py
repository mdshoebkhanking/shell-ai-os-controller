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
    assert "runSpeechReaction" in dashboard
    assert "amplitudeFrames" in dashboard
    assert "durationMs" in dashboard
    assert "backendLevel" in sphere
    assert "speechPulse" in sphere
    assert "idlePulse" in sphere


def test_dashboard_queued_tts_does_not_start_orb_reaction():
    dashboard = (ROOT / "shell_web_ui" / "src" / "views" / "Dashboard.tsx").read_text(encoding="utf-8")
    speak_shell = dashboard.split("const speakShell = useCallback", 1)[1].split("useEffect", 1)[0]
    queued_branch = speak_shell.split("if ((result as any)?.queued)", 1)[1].split("setSpeechState('SPEAKING')", 1)[0]
    speech_status = dashboard.split("const onSpeechStatus", 1)[1].split("const onChatUpdated", 1)[0]

    assert "setSpeechState('VOICE QUEUED')" in speak_shell
    assert "setVoiceAmplitude(0)" in queued_branch
    assert "runSpeechReaction" not in queued_branch
    assert "state === 'QUEUED'" in speech_status
    assert speech_status.index("state === 'QUEUED'") < speech_status.index("state === 'SPEAKING'")


def test_backend_probe_voice_amplitude_channel_is_env_gated(monkeypatch):
    from PyQt6.QtCore import QCoreApplication
    import shell_web_ui.host as host

    QCoreApplication.instance() or QCoreApplication([])
    bridge = host.ShellBackendBridge()
    emitted = []
    monkeypatch.setattr(bridge, "emit_event", lambda channel, payload: emitted.append((channel, payload)))

    monkeypatch.delenv("SHELL_UI_PROBE_ENABLED", raising=False)
    disabled = bridge._dispatch("probe-voice-amplitude", [{"value": 0.9}])
    assert disabled["success"] is False
    assert emitted == []

    monkeypatch.setenv("SHELL_UI_PROBE_ENABLED", "1")
    enabled = bridge._dispatch("probe-voice-amplitude", [{"value": 0.9, "speaking": True}])
    assert enabled["success"] is True
    assert ("voice-amplitude", {"value": 0.9, "probe": True}) in emitted
    assert any(channel == "speech-status" and payload["state"] == "speaking" for channel, payload in emitted)


def test_browser_probe_emitter_is_query_param_gated():
    bridge = (ROOT / "shell_web_ui" / "src" / "shellBridge.ts").read_text(encoding="utf-8")

    assert "shell-ui-probe" in bridge
    assert "__shellProbeEmit" in bridge
    assert "window.location.search" in bridge


def test_primary_tabs_can_scroll_inside_tight_windows():
    shell_ai = (ROOT / "shell_web_ui" / "src" / "UI" / "ShellAI.tsx").read_text(encoding="utf-8")
    css = (ROOT / "shell_web_ui" / "src" / "assets" / "main.css").read_text(encoding="utf-8")

    assert "shell-primary-tabs" in shell_ai
    assert "flex-1 items-center justify-center" in shell_ai
    assert ".shell-primary-tabs" in css
    assert "overflow-x: auto" in css


def test_orb_session_dock_keeps_accessible_icon_controls():
    dashboard = (ROOT / "shell_web_ui" / "src" / "views" / "Dashboard.tsx").read_text(encoding="utf-8")
    css = (ROOT / "shell_web_ui" / "src" / "assets" / "main.css").read_text(encoding="utf-8")
    sphere = (ROOT / "shell_web_ui" / "src" / "components" / "Sphere.tsx").read_text(encoding="utf-8")

    assert "shell-orb-dock-anchor" in dashboard
    assert dashboard.count('type="button"') >= 4
    assert "aria-pressed={isSystemActive}" in dashboard
    assert "aria-pressed={!isMicMuted}" in dashboard
    assert "shell-orb-fallback" in sphere
    assert "shell-orb-stage-speaking" in sphere
    assert "resize={{ scroll: false" in sphere
    assert ".shell-orb-fallback" in css
    assert ".shell-orb-canvas" in css
    assert ".shell-orb-dock-anchor" in css
    assert "bottom: clamp(72px, 8vh, 118px)" in css
    assert "touch-action: manipulation" in css
    assert "min-width: 50px" in css
    assert ".shell-dock-button:focus-visible" in css
    assert ".shell-dock-button svg" in css
    assert ".shell-dock-button-main.shell-dock-button-live" in css
