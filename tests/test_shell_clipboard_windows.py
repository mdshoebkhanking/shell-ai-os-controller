def test_windows_clipboard_copy_prefers_powershell(monkeypatch):
    import shell_clipboard

    calls = []

    class Result:
        returncode = 0
        stdout = ""

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return Result()

    monkeypatch.setattr(shell_clipboard.sys, "platform", "win32")
    monkeypatch.setattr(shell_clipboard.subprocess, "run", fake_run)

    assert shell_clipboard._copy_to_clipboard("hello") is True
    assert calls
    assert calls[0][0][:3] == ["powershell", "-NoProfile", "-Command"]
    assert calls[0][1]["input"] == "hello"


def test_windows_clipboard_paste_prefers_powershell(monkeypatch):
    import shell_clipboard

    class Result:
        returncode = 0
        stdout = "hello\r\n"

    monkeypatch.setattr(shell_clipboard.sys, "platform", "win32")
    monkeypatch.setattr(shell_clipboard.subprocess, "run", lambda *_args, **_kwargs: Result())

    assert shell_clipboard._read_from_clipboard() == "hello"
