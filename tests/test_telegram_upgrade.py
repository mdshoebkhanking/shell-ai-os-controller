import pytest


def test_telegram_command_analytics_handles_first_command(monkeypatch, tmp_path):
    import shell_telegram

    monkeypatch.chdir(tmp_path)
    analytics = shell_telegram.BotAnalytics()

    analytics.log_command("/start")
    analytics.log_command("/start")

    assert analytics.stats["total_commands"] == 2
    assert analytics.stats["commands"]["/start"] == 2


def test_telegram_security_accepts_allowed_chat_id_with_different_user(monkeypatch):
    import shell_telegram

    monkeypatch.setenv("SHELL_TELEGRAM_ALLOWED_CHAT_IDS", "222")
    monkeypatch.setenv("SHELL_TELEGRAM_BLOCKED_CHAT_IDS", "")
    shell_telegram._reload_runtime_config()

    security = shell_telegram.SecurityManager()

    assert security.is_user_allowed(chat_id=222, user_id=111) is True
    assert security.is_user_allowed(chat_id=333, user_id=111) is False


@pytest.mark.asyncio
async def test_telegram_message_uses_chat_id_for_access_and_memory(monkeypatch, tmp_path):
    import shell_telegram

    class FakeAPI:
        def __init__(self):
            self.messages = []
            self.actions = []

        async def send_message(self, chat_id, text, parse_mode="Markdown", reply_markup=None):
            self.messages.append((chat_id, text, parse_mode, reply_markup))
            return True

        async def send_chat_action(self, chat_id, action="typing"):
            self.actions.append((chat_id, action))
            return {"ok": True}

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SHELL_TELEGRAM_ALLOWED_CHAT_IDS", "222")
    monkeypatch.setenv("SHELL_TELEGRAM_BLOCKED_CHAT_IDS", "")
    shell_telegram._reload_runtime_config()
    monkeypatch.setattr(shell_telegram.Config, "USERS_FILE", tmp_path / "users.json")

    bot = shell_telegram.ShellTelegramBot()
    bot.api = FakeAPI()

    async def fake_smart_execute(chat_id, user_id, user_name, text):
        return "Shell reply"

    monkeypatch.setattr(bot, "_smart_execute", fake_smart_execute)

    await bot._handle_message({
        "chat": {"id": 222},
        "from": {"id": 111, "first_name": "Tester", "username": "tester"},
        "text": "hello shell",
    })

    sent_text = "\n".join(msg[1] for msg in bot.api.messages)
    assert "Access denied" not in sent_text
    assert "222" in sent_text
    assert bot.memory.get_history(222)
    assert bot.memory.get_history(111) == []


@pytest.mark.asyncio
async def test_telegram_send_message_fallback_removes_null_parse_mode(monkeypatch):
    import shell_telegram

    api = shell_telegram.TelegramAPI("123456:" + "A" * 30)
    calls = []

    async def fake_request(method, params=None, files=None):
        calls.append(dict(params or {}))
        return {"ok": len(calls) > 1}

    monkeypatch.setattr(api, "request", fake_request)

    ok = await api.send_message(123, "*hello*", reply_markup={"inline_keyboard": []})

    assert ok is True
    assert calls[0]["parse_mode"] == "Markdown"
    assert isinstance(calls[0]["reply_markup"], dict)
    assert "parse_mode" not in calls[1]


def test_telegram_status_reports_diagnostics(monkeypatch):
    import asyncio
    import shell_telegram

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:" + "A" * 30)
    monkeypatch.setenv("SHELL_TELEGRAM_ALLOWED_CHAT_IDS", "222")
    monkeypatch.setenv("SHELL_TELEGRAM_REMOTE_CONTROL_ENABLED", "1")
    monkeypatch.setenv("SHELL_TELEGRAM_ALLOW_TERMINAL", "0")
    shell_telegram._reload_runtime_config()
    shell_telegram.bot.active = False
    shell_telegram.bot.last_error = "poll conflict"

    status = asyncio.run(shell_telegram.telegram_bot_status())

    assert "Token: configured" in status
    assert "PC control: ON" in status
    assert "Allowed chats: 1" in status
    assert "poll conflict" in status


@pytest.mark.asyncio
async def test_telegram_start_uses_durable_background_polling_loop(monkeypatch, tmp_path):
    import asyncio
    import shell_telegram

    class FakeTelegramAPI:
        last_error = ""

        def __init__(self, token=None):
            self.token = token

        async def get_me(self):
            return {"ok": True, "result": {"username": "shell_test_bot", "first_name": "Shell Test"}}

        async def request(self, method, params=None, files=None):
            await asyncio.sleep(0.02)
            return {"ok": True, "result": []}

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(shell_telegram.Config, "USERS_FILE", tmp_path / "users.json")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:" + "A" * 30)
    shell_telegram._reload_runtime_config()
    monkeypatch.setattr(shell_telegram, "TelegramAPI", FakeTelegramAPI)

    bot = shell_telegram.ShellTelegramBot()
    started = await bot.start()

    assert "STARTED" in started
    assert bot._task_running() is True
    assert bot.thread is not None and bot.thread.is_alive()

    stopped = await bot.stop()

    assert "stopped" in stopped.lower()
    assert bot.active is False
