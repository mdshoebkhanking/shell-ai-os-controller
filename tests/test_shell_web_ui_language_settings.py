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
    assert "selfIdentityReply" in bridge
    assert "tum\\s+kon" in bridge
    assert "Browser speech fallback is disabled" in bridge
    assert "Current Shell language setting" in voice
    assert "shellLanguageInstruction" in voice
    assert "shellSpeechInstruction()" in root
    assert "speechSynthesis" not in dashboard


def test_dashboard_local_voice_does_not_fall_back_to_browser_speech():
    dashboard = read_project_file("shell_web_ui/src/views/Dashboard.tsx")
    speak_shell = dashboard.split("const speakShell = useCallback", 1)[1].split("}, [speakRealVoice, voiceRuntime])", 1)[0]

    assert "window.shellAPI?.speakText?.(speechText)" in speak_shell
    assert "speakWithBrowser" not in dashboard
    assert "browser-speech" not in dashboard
    assert "setSpeechState('VOICE ERR')" in speak_shell
    assert "let didSendToRealVoice = false" in speak_shell
    assert "didSendToRealVoice = await speakRealVoice(speechText)" in speak_shell


def test_dashboard_voice_test_startup_text_is_english():
    dashboard = read_project_file("shell_web_ui/src/views/Dashboard.tsx")

    assert "import { normalizeGeminiApiKey } from '@renderer/services/api-key-utils'" in dashboard
    assert "const hasBrowserGeminiVoiceKey = () =>" in dashboard
    assert "const useGeminiTestVoice = voiceRuntime === 'gemini' && hasBrowserGeminiVoiceKey()" in dashboard
    assert "Premium Gemini voice is active. Your private command center is standing by." in dashboard
    assert "Command center ready." in dashboard
    assert "voice ready hai" not in dashboard
    assert "bol raha hoon" not in dashboard


def test_gemini_voice_without_key_falls_through_to_backend_voice():
    root = read_project_file("shell_web_ui/src/IndexRoot.tsx")

    assert "import { normalizeGeminiApiKey } from './services/api-key-utils'" in root
    assert "const hasGeminiVoiceKey = async () =>" in root
    assert "const localKey = normalizeGeminiApiKey(localStorage.getItem('shell_custom_api_key'))" in root
    assert "if (!desktopBridgeExpected()) return false" in root
    assert "if (!(await hasGeminiVoiceKey())) return false" in root
    speak_real_voice = root.split("const speakRealVoice = async", 1)[1].split("const startVision = async", 1)[0]
    assert speak_real_voice.index("if (!(await hasGeminiVoiceKey())) return false") < speak_real_voice.index(
        "await shellService.connect()"
    )


def test_settings_hides_kokoro_tts_card_and_separates_voice_from_models():
    settings = read_project_file("shell_web_ui/src/views/Settings.tsx")
    bridge = read_project_file("shell_web_ui/src/shellBridge.ts")

    assert "offline-tts-status" in settings
    assert "offline-llm-status" in settings
    assert "offline-llm-catalog" in settings
    assert "offline-llm-download" in settings
    assert "offline-llm-select" in settings
    assert "offline-coding-llm-status" in settings
    assert "offline-coding-llm-catalog" in settings
    assert "offline-coding-llm-download" in settings
    assert "offline-coding-llm-select" in settings
    assert "applyOfflineTtsStatus" in settings
    assert "applyOfflineLlmStatus" in settings
    assert "downloadOfflineModel" in settings
    assert "selectOfflineModel" in settings
    assert "isSelected ? 'ACTIVE'" in settings
    assert "refreshOfflineTtsStatus" in settings
    assert "refreshOfflineLlmStatus" in settings
    assert "OFFLINE BRAIN" in settings
    assert "OFFLINE CODING BRAIN" in settings
    assert "applyOfflineCodingLlmStatus" in settings
    assert "downloadOfflineCodingModel" in settings
    assert "selectOfflineCodingModel" in settings
    assert "OFFLINE TTS" not in settings
    assert "LOCAL ONLY" not in settings
    assert "{ id: 'backend'" not in settings
    assert "AUTO LOCAL" in settings
    assert "GEMINI LIVE" in settings
    assert "OS Voice Profile" in settings
    assert "OS Voice Profile" in settings.split("OFFLINE BRAIN", 1)[0]
    assert settings.index("OS Voice Profile") < settings.index("OFFLINE BRAIN")
    assert '<div className={`${cardClass} md:col-span-2`}>' in settings
    assert "offlineLlmCandidateSummary" in settings
    assert "Shell will use local OS voice fallback" not in settings
    assert "will not use local OS TTS fallback" in settings
    assert "Browser speech fallback is disabled" in bridge
    assert "case 'offline-tts-status'" in bridge
    assert "case 'offline-llm-status'" in bridge
    assert "case 'offline-llm-catalog'" in bridge
    assert "case 'offline-llm-download'" in bridge
    assert "case 'offline-llm-select'" in bridge
    assert "case 'offline-coding-llm-status'" in bridge
    assert "case 'offline-coding-llm-catalog'" in bridge
    assert "case 'offline-coding-llm-download'" in bridge
    assert "case 'offline-coding-llm-select'" in bridge
    assert "settingsTabs = [" in settings
    assert "OFFLINE BRAIN" not in settings.split("settingsTabs = [", 1)[1].split("]", 1)[0]
    assert "generalHydratedRef" in settings
    assert "keysHydratedRef" in settings
    assert "activeTab !== 'general'" in settings
    assert "activeTab !== 'keys'" in settings
    assert "removeAllListeners('updater-event')" not in settings
    assert "ipcRenderer?.off?.('updater-event'" in settings


def test_webengine_host_exposes_settings_channels_and_language_prompt():
    host = read_project_file("shell_web_ui/host.py")

    assert '"get-settings": self._get_settings' in host
    assert '"set-settings": self._set_settings' in host
    assert '"offline-llm-status": self._offline_llm_status' in host
    assert '"offline-llm-catalog": self._offline_llm_catalog' in host
    assert '"offline-llm-download": self._offline_llm_download' in host
    assert '"offline-llm-select": self._offline_llm_select' in host
    assert '"offline-coding-llm-status": self._offline_coding_llm_status' in host
    assert '"offline-coding-llm-catalog": self._offline_coding_llm_catalog' in host
    assert '"offline-coding-llm-download": self._offline_coding_llm_download' in host
    assert '"offline-coding-llm-select": self._offline_coding_llm_select' in host
    assert "from shell_settings_manager import get_settings" in host
    assert "from shell_settings_manager import set_settings" in host
    assert "ALLOWED_SHELL_LANGUAGES = {\"hinglish\", \"english\", \"hindi\"}" in host
    assert "_shell_language_instruction()" in host
