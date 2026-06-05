from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_project_file(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_shell_language_options_are_limited_to_three_choices():
    source = read_project_file("shell_web_ui/src/services/language-settings.ts")

    assert "export type ShellLanguage = 'hinglish' | 'english' | 'hindi'" in source
    assert source.count("id: 'hinglish'") == 1
    assert source.count("id: 'english'") == 1
    assert source.count("id: 'hindi'") == 1
    assert "SHELL_LANGUAGE_STORAGE_KEY = 'shell_language'" in source


def test_settings_language_picker_persists_frontend_and_backend_setting():
    settings = read_project_file("shell_web_ui/src/views/Settings.tsx")

    assert "Shell Language" in settings
    assert "SHELL_LANGUAGE_OPTIONS.map" in settings
    assert "localStorage.setItem(SHELL_LANGUAGE_STORAGE_KEY, nextLanguage)" in settings
    assert "window.dispatchEvent(new CustomEvent('shell-language-changed'" in settings
    assert "window.electron.ipcRenderer.invoke('set-settings'" in settings
    assert "language: nextLanguage" in settings
    assert "shell_language: nextLanguage" in settings


def test_language_setting_reaches_browser_bridge_and_gemini_live_prompt():
    bridge = read_project_file("shell_web_ui/src/shellBridge.ts")
    voice = read_project_file("shell_web_ui/src/services/shell-voice-ai.ts")
    root = read_project_file("shell_web_ui/src/IndexRoot.tsx")
    dashboard = read_project_file("shell_web_ui/src/views/Dashboard.tsx")

    assert "case 'get-settings'" in bridge
    assert "case 'set-settings'" in bridge
    assert "languageReply" in bridge
    assert "utterance.lang = shellSpeechLocale()" in bridge
    assert "Current Shell language setting" in voice
    assert "shellLanguageInstruction" in voice
    assert "shellSpeechInstruction()" in root
    assert "utterance.lang = shellSpeechLocale()" in dashboard


def test_settings_exposes_offline_tts_status_without_extra_tab():
    settings = read_project_file("shell_web_ui/src/views/Settings.tsx")
    bridge = read_project_file("shell_web_ui/src/shellBridge.ts")

    assert "offline-tts-status" in settings
    assert "offline-llm-status" in settings
    assert "applyOfflineTtsStatus" in settings
    assert "applyOfflineLlmStatus" in settings
    assert "refreshOfflineTtsStatus" in settings
    assert "refreshOfflineLlmStatus" in settings
    assert "OFFLINE TTS" in settings
    assert "OFFLINE BRAIN" in settings
    assert "offlineTtsCandidateSummary" in settings
    assert "offlineLlmCandidateSummary" in settings
    assert "Browser speech fallback" in bridge
    assert "case 'offline-tts-status'" in bridge
    assert "case 'offline-llm-status'" in bridge
    assert "settingsTabs = [" in settings
    assert "OFFLINE TTS" not in settings.split("settingsTabs = [", 1)[1].split("]", 1)[0]
    assert "OFFLINE BRAIN" not in settings.split("settingsTabs = [", 1)[1].split("]", 1)[0]


def test_webengine_host_exposes_settings_channels_and_language_prompt():
    host = read_project_file("shell_web_ui/host.py")

    assert '"get-settings": self._get_settings' in host
    assert '"set-settings": self._set_settings' in host
    assert '"offline-llm-status": self._offline_llm_status' in host
    assert "from shell_settings_manager import get_settings" in host
    assert "from shell_settings_manager import set_settings" in host
    assert "ALLOWED_SHELL_LANGUAGES = {\"hinglish\", \"english\", \"hindi\"}" in host
    assert "_shell_language_instruction()" in host
