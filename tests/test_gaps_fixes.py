import pytest
import imaplib
import json
import asyncio
import re
import shell_app_context
import shell_email_tool
import shell_diagnostics


def parse_tool_json(s):
    cleaned = re.sub(r"\s*\[Tool Execution:\s*[^\]]+\]\s*$", "", s, flags=re.I | re.S).strip()
    return json.loads(cleaned)


def test_active_window_windows_browser(monkeypatch):
    # Mock _run_text to simulate powershell output
    def mock_run(command, timeout=4):
        return '{"app_name": "chrome", "process_name": "chrome", "title": "Example", "url": "example.com"}'
    
    monkeypatch.setattr(shell_app_context, "_run_text", mock_run)
    
    info = shell_app_context._active_window_windows()
    assert info.app_name == "chrome"
    assert info.title == "Example"
    assert info.url == "https://example.com"


def test_active_window_windows_non_browser(monkeypatch):
    # Mock _run_text for non-browser
    def mock_run(command, timeout=4):
        return '{"app_name": "notepad", "process_name": "notepad", "title": "Untitled", "url": ""}'
        
    monkeypatch.setattr(shell_app_context, "_run_text", mock_run)
    
    info = shell_app_context._active_window_windows()
    assert info.app_name == "notepad"
    assert info.title == "Untitled"
    assert info.url == ""


class MockGmailService:
    def __init__(self):
        self._last_call = None

    def users(self):
        return self

    def messages(self):
        return self

    def drafts(self):
        return self

    def list(self, *args, **kwargs):
        self._last_call = "list"
        return self

    def get(self, *args, **kwargs):
        self._last_call = "get"
        return self

    def create(self, *args, **kwargs):
        self._last_call = "create"
        return self

    def execute(self):
        if self._last_call == "list":
            return {"messages": [{"id": "msg123"}, {"id": "msg456"}]}
        if self._last_call == "get":
            return {
                "payload": {
                    "headers": [
                        {"name": "Subject", "value": "Test Subject"},
                        {"name": "From", "value": "sender@example.com"},
                        {"name": "Date", "value": "Mon, 08 Jun 2026 12:00:00 -0700"}
                    ]
                },
                "snippet": "This is the body snippet content."
            }
        if self._last_call == "create":
            return {"id": "draft123"}
        return {}


def test_gmail_read_inbox_success(monkeypatch):
    monkeypatch.setattr(shell_email_tool, "_is_gmail_api_configured", lambda: True)
    monkeypatch.setattr(shell_email_tool, "_get_gmail_service", lambda: MockGmailService())
    
    res_str = asyncio.run(shell_email_tool.gmail_read_inbox_tool(max_results=2))
    res = parse_tool_json(res_str)
    
    assert res["success"] is True
    assert len(res["emails"]) == 2
    assert res["emails"][0]["from"] == "sender@example.com"
    assert res["emails"][0]["subject"] == "Test Subject"
    assert "body snippet content" in res["emails"][0]["snippet"]


def test_gmail_read_inbox_login_failed(monkeypatch):
    monkeypatch.setattr(shell_email_tool, "_is_gmail_api_configured", lambda: False)
    
    res_str = asyncio.run(shell_email_tool.gmail_read_inbox_tool())
    res = parse_tool_json(res_str)
    
    assert res["success"] is False
    assert "not configured" in res["error"].lower()


def test_gmail_create_draft_success(monkeypatch):
    monkeypatch.setattr(shell_email_tool, "_is_gmail_api_configured", lambda: True)
    monkeypatch.setattr(shell_email_tool, "_get_gmail_service", lambda: MockGmailService())
    
    res_str = asyncio.run(shell_email_tool.gmail_create_draft_tool(
        to="rec@example.com",
        subject="Draft Subject",
        body="Draft Body"
    ))
    res = parse_tool_json(res_str)
    assert res["success"] is True
    assert res["error"] is None


def test_send_email_tool_returns_json(monkeypatch):
    monkeypatch.setattr(shell_email_tool, "_is_gmail_api_configured", lambda: True)
    monkeypatch.setattr(shell_email_tool, "_send_email_via_gmail_api", lambda *args, **kwargs: True)
    
    res_str = asyncio.run(shell_email_tool.send_email_tool(
        recipient="target@example.com",
        subject="Hello",
        body="World"
    ))
    res = parse_tool_json(res_str)
    assert res["success"] is True
    assert res["error"] is None


def test_voice_diagnostics_all_ok(monkeypatch):
    import sys
    from types import ModuleType
    
    # Mock sounddevice module
    fake_sd = ModuleType("sounddevice")
    def mock_query():
        return [
            {"name": "Mock Mic", "max_input_channels": 2, "max_output_channels": 0},
            {"name": "Mock Speaker", "max_input_channels": 0, "max_output_channels": 2}
        ]
    fake_sd.query_devices = mock_query
    monkeypatch.setitem(sys.modules, "sounddevice", fake_sd)
    
    # Mock Kokoro model find
    import shell_offline_tts
    monkeypatch.setattr(shell_offline_tts, "_find_kokoro_model", lambda paths: ("/path/to/kokoro.onnx", "/path/to/voices.bin", "/path/to"))
    
    # Mock Sherpa model config
    import shell_local_stt
    class MockConfig:
        tokens = "/path/to/tokens.txt"
        encoder = "/path/to/encoder.onnx"
        decoder = "/path/to/decoder.onnx"
        joiner = "/path/to/joiner.onnx"
        model_dir = "/path/to"
        
        def to_dict(self):
            return {}
        def missing_reason(self):
            return ""
            
    monkeypatch.setattr(shell_local_stt.LocalSTTConfig, "from_environment", lambda: MockConfig())
    
    res_str = asyncio.run(shell_diagnostics.diagnose_voice_hardware_tool())
    res = parse_tool_json(res_str)
    
    assert res["ok"] is True
    assert res["microphone"]["present"] is True
    assert "Mock Mic" in res["microphone"]["details"]
    assert res["speaker"]["present"] is True
    assert "Mock Speaker" in res["speaker"]["details"]
    assert res["kokoro_model"]["present"] is True
    assert res["kokoro_model"]["path"] == "/path/to/kokoro.onnx"
    assert res["sherpa_models"]["present"] is True
    assert res["sherpa_models"]["missing_files"] == []


def test_voice_diagnostics_missing_all(monkeypatch):
    import sys
    from types import ModuleType
    
    # Mock sounddevice query returning no devices
    fake_sd = ModuleType("sounddevice")
    fake_sd.query_devices = lambda: []
    monkeypatch.setitem(sys.modules, "sounddevice", fake_sd)
    
    # Mock Kokoro not found
    import shell_offline_tts
    monkeypatch.setattr(shell_offline_tts, "_find_kokoro_model", lambda paths: (None, None, None))
    
    # Mock Sherpa missing files
    import shell_local_stt
    class MockConfigEmpty:
        tokens = None
        encoder = None
        decoder = None
        joiner = None
        model_dir = None
        
        def to_dict(self):
            return {}
        def missing_reason(self):
            return "missing"
            
    monkeypatch.setattr(shell_local_stt.LocalSTTConfig, "from_environment", lambda: MockConfigEmpty())
    
    res_str = asyncio.run(shell_diagnostics.diagnose_voice_hardware_tool())
    res = parse_tool_json(res_str)
    
    assert res["ok"] is False
    assert res["microphone"]["present"] is False
    assert res["speaker"]["present"] is False
    assert res["kokoro_model"]["present"] is False
    assert res["kokoro_model"]["path"] is None
    assert res["sherpa_models"]["present"] is False
    assert "tokens.txt" in res["sherpa_models"]["missing_files"]
    assert "encoder-epoch-99-avg-1.int8.onnx" in res["sherpa_models"]["missing_files"]


def test_react_agent_success(monkeypatch):
    from shell_agents import DeveloperAgent
    agent = DeveloperAgent()
    
    calls = []
    # Mock _ai_think to return plans
    async def mock_think(prompt, system_prompt=None, mode=None):
        calls.append(prompt)
        if prompt.startswith("Analyze this development task"):
            return "Need to check files first."
        elif "Your execution history so far" in prompt:
            if "check files" not in prompt:
                return json.dumps({
                    "completed": False,
                    "next_step": {
                        "action": "check files",
                        "tool": "brain", # Use brain tool to avoid registry requirement
                        "params": {"prompt": "some prompt"}
                    }
                })
            else:
                return json.dumps({
                    "completed": True,
                    "final_summary": "Task done successfully!"
                })
        elif prompt.startswith("Review the work done"):
            return "Code looks good."
        else:
            return "Task done successfully!"
            
    monkeypatch.setattr(agent, "_ai_think", mock_think)
    
    res = asyncio.run(agent.execute("simple task"))
    assert "success" in res
    assert "Task done successfully!" in res


def test_react_agent_self_healing(monkeypatch):
    from shell_agents import DeveloperAgent
    agent = DeveloperAgent()
    
    calls = []
    async def mock_think(prompt, system_prompt=None, mode=None):
        calls.append(prompt)
        if prompt.startswith("Analyze this development task"):
            return "Need to write file."
        elif "Your execution history so far" in prompt:
            if "try direct write" not in prompt:
                return json.dumps({
                    "completed": False,
                    "next_step": {
                        "action": "try direct write",
                        "tool": "mock_failing_tool",
                        "params": {}
                    }
                })
            elif "Error: Permission Denied" in prompt:
                return json.dumps({
                    "completed": True,
                    "final_summary": "Healed and completed via fallback!"
                })
            else:
                return json.dumps({
                    "completed": True,
                    "final_summary": "Direct completion"
                })
        elif prompt.startswith("Review the work done"):
            return "Looks good."
        else:
            return "Healed and completed via fallback!"
            
    # Mock registry to return a failing tool
    class MockRegistry:
        def get_tool_obj(self, name):
            if name == "mock_failing_tool":
                async def failing_fn(**kwargs):
                    return "Error: Permission Denied"
                return failing_fn
            return None
        def record_call(self, name):
            pass
        def get_by_category(self, cat):
            return []

    monkeypatch.setattr(agent, "_ai_think", mock_think)
    monkeypatch.setattr(agent, "_get_registry", lambda: MockRegistry())
    
    res = asyncio.run(agent.execute("write file task"))
    assert "success" in res
    assert "Healed and completed via fallback!" in res


def test_gmail_api_is_gmail_api_configured_default(monkeypatch):
    monkeypatch.setenv("SHELL_GMAIL_CREDENTIALS_JSON", "nonexistent_creds.json")
    monkeypatch.setenv("SHELL_GMAIL_TOKEN_JSON", "nonexistent_token.json")
    assert shell_email_tool._is_gmail_api_configured() is False


def test_gmail_api_setup_status_no_api_configured(monkeypatch):
    monkeypatch.setenv("SHELL_GMAIL_CREDENTIALS_JSON", "nonexistent_creds.json")
    monkeypatch.setenv("SHELL_GMAIL_TOKEN_JSON", "nonexistent_token.json")
    monkeypatch.setenv("SHELL_SENDER_EMAIL", "")
    monkeypatch.setenv("SHELL_SENDER_PASSWORD", "")
    
    status = asyncio.run(shell_email_tool.email_setup_status_tool())
    assert "not configured" in status.lower()


def test_gmail_api_configured_missing_libs(monkeypatch, tmp_path):
    creds_file = tmp_path / "credentials.json"
    creds_file.write_text("{}", encoding="utf-8")
    
    monkeypatch.setenv("SHELL_GMAIL_CREDENTIALS_JSON", str(creds_file))
    monkeypatch.setenv("SHELL_GMAIL_TOKEN_JSON", "nonexistent_token.json")
    
    def mock_get_service():
        raise ImportError("Gmail API client libraries are missing")
    monkeypatch.setattr(shell_email_tool, "_get_gmail_service", mock_get_service)
    
    monkeypatch.setenv("SHELL_SENDER_EMAIL", "")
    monkeypatch.setenv("SHELL_SENDER_PASSWORD", "")
    res = asyncio.run(shell_email_tool.gmail_read_inbox_tool())
    assert "gmail api client libraries are missing" in res.lower() or "failed" in res.lower()

