import sys
import time
import types


def _install_fake_sherpa(monkeypatch, text="open calculator"):
    calls = {}

    class FakeResult:
        def __init__(self, value):
            self.text = value

    class FakeStream:
        def __init__(self):
            self.accepted = []
            self.finished = False
            self.decoded = False

        def accept_waveform(self, sample_rate, samples):
            self.accepted.append((sample_rate, len(samples)))

        def input_finished(self):
            self.finished = True

    class FakeRecognizer:
        @classmethod
        def from_transducer(cls, **kwargs):
            calls["from_transducer"] = kwargs
            return cls()

        def create_stream(self):
            return FakeStream()

        def is_ready(self, stream):
            return not stream.decoded and bool(stream.accepted)

        def decode_stream(self, stream):
            stream.decoded = True

        def get_result(self, stream):
            return FakeResult(text if stream.decoded or stream.finished else "")

    fake = types.SimpleNamespace(OnlineRecognizer=FakeRecognizer)
    fake.__spec__ = types.SimpleNamespace()
    monkeypatch.setitem(sys.modules, "sherpa_onnx", fake)

    import shell_local_stt

    monkeypatch.setattr(shell_local_stt.importlib.util, "find_spec", lambda name: object() if name == "sherpa_onnx" else None)
    return calls


def _install_fake_offline_sherpa(monkeypatch, text="namaste shell"):
    calls = {}

    class FakeResult:
        def __init__(self, value):
            self.text = value

    class FakeOfflineStream:
        def __init__(self):
            self.accepted = []
            self.finished = False
            self.result = FakeResult("")

        def accept_waveform(self, sample_rate, samples):
            self.accepted.append((sample_rate, len(samples)))

        def input_finished(self):
            self.finished = True

    class FakeOfflineRecognizer:
        @classmethod
        def from_whisper(cls, **kwargs):
            calls["from_whisper"] = kwargs
            return cls()

        @classmethod
        def from_sense_voice(cls, **kwargs):
            calls["from_sense_voice"] = kwargs
            return cls()

        def create_stream(self):
            return FakeOfflineStream()

        def decode_stream(self, stream):
            stream.result = FakeResult(text)

    fake = types.SimpleNamespace(OfflineRecognizer=FakeOfflineRecognizer)
    fake.__spec__ = types.SimpleNamespace()
    monkeypatch.setitem(sys.modules, "sherpa_onnx", fake)

    import shell_local_stt

    monkeypatch.setattr(shell_local_stt.importlib.util, "find_spec", lambda name: object() if name == "sherpa_onnx" else None)
    return calls


def test_local_stt_flag_default_off_without_bundled_model(monkeypatch, tmp_path):
    monkeypatch.delenv("SHELL_LOCAL_STT_ENABLED", raising=False)
    import shell_local_stt
    monkeypatch.setattr(shell_local_stt, "DEFAULT_LOCAL_STT_MODEL_DIRS", (tmp_path / "missing",))

    from shell_local_stt import LocalSTTConfig, local_stt_enabled

    assert local_stt_enabled() is False
    assert LocalSTTConfig.from_environment().missing_reason() == "No bundled local STT model is configured."


def test_local_stt_auto_enables_when_bundled_model_exists(monkeypatch, tmp_path):
    monkeypatch.delenv("SHELL_LOCAL_STT_ENABLED", raising=False)
    _install_fake_sherpa(monkeypatch)
    for name in (
        "tokens.txt",
        "encoder-epoch-99-avg-1.int8.onnx",
        "decoder-epoch-99-avg-1.onnx",
        "joiner-epoch-99-avg-1.int8.onnx",
    ):
        (tmp_path / name).write_text("x", encoding="utf-8")

    import shell_local_stt

    monkeypatch.setattr(shell_local_stt, "DEFAULT_LOCAL_STT_MODEL_DIRS", (tmp_path,))

    cfg = shell_local_stt.LocalSTTConfig.from_environment()
    assert shell_local_stt.local_stt_enabled() is True
    assert cfg.missing_reason() == ""
    assert cfg.to_dict()["autoEnabled"] is True


def test_local_stt_explicit_disable_overrides_bundled_model(monkeypatch, tmp_path):
    monkeypatch.setenv("SHELL_LOCAL_STT_ENABLED", "0")
    _install_fake_sherpa(monkeypatch)
    for name in (
        "tokens.txt",
        "encoder-epoch-99-avg-1.int8.onnx",
        "decoder-epoch-99-avg-1.onnx",
        "joiner-epoch-99-avg-1.int8.onnx",
    ):
        (tmp_path / name).write_text("x", encoding="utf-8")

    import shell_local_stt

    monkeypatch.setattr(shell_local_stt, "DEFAULT_LOCAL_STT_MODEL_DIRS", (tmp_path,))

    assert shell_local_stt.local_stt_enabled() is False
    assert shell_local_stt.LocalSTTConfig.from_environment().missing_reason() == "SHELL_LOCAL_STT_ENABLED=0"


def test_local_stt_config_auto_resolves_transducer_model(monkeypatch, tmp_path):
    monkeypatch.setenv("SHELL_LOCAL_STT_ENABLED", "1")
    monkeypatch.setenv("SHELL_LOCAL_STT_MODEL_DIR", str(tmp_path))
    _install_fake_sherpa(monkeypatch)

    for name in (
        "tokens.txt",
        "encoder-epoch-99-avg-1.int8.onnx",
        "decoder-epoch-99-avg-1.onnx",
        "joiner-epoch-99-avg-1.onnx",
    ):
        (tmp_path / name).write_text("x", encoding="utf-8")

    from shell_local_stt import LocalSTTConfig

    cfg = LocalSTTConfig.from_environment()
    assert cfg.configured_kind() == "transducer"
    assert cfg.missing_reason() == ""
    assert cfg.encoder and "int8" in cfg.encoder.name


def test_sherpa_streaming_stt_transcribes_with_fake_recognizer(monkeypatch, tmp_path):
    monkeypatch.setenv("SHELL_LOCAL_STT_ENABLED", "1")
    monkeypatch.setenv("SHELL_LOCAL_STT_MODEL_DIR", str(tmp_path))
    calls = _install_fake_sherpa(monkeypatch, text="open calculator")

    for name in (
        "tokens.txt",
        "encoder.onnx",
        "decoder.onnx",
        "joiner.onnx",
    ):
        (tmp_path / name).write_text("x", encoding="utf-8")

    import numpy as np
    from shell_local_stt import SherpaOnnxStreamingSTT

    stt = SherpaOnnxStreamingSTT.from_environment()
    result = stt.transcribe(np.ones(1600, dtype=np.int16), sample_rate=16000)

    assert result.ok is True
    assert result.text == "open calculator"
    assert result.elapsed_ms < 500
    assert calls["from_transducer"]["sample_rate"] == 16000


def test_sherpa_offline_whisper_transcribes_with_language_flag(monkeypatch, tmp_path):
    monkeypatch.setenv("SHELL_LOCAL_STT_ENABLED", "1")
    monkeypatch.setenv("SHELL_LOCAL_STT_MODEL_KIND", "whisper")
    monkeypatch.setenv("SHELL_LOCAL_STT_MODEL_DIR", str(tmp_path))
    monkeypatch.setenv("SHELL_LOCAL_STT_LANGUAGE", "hi")
    calls = _install_fake_offline_sherpa(monkeypatch, text="namaste shell")

    for name in (
        "tokens.txt",
        "tiny-encoder.int8.onnx",
        "tiny-decoder.int8.onnx",
    ):
        (tmp_path / name).write_text("x", encoding="utf-8")

    import numpy as np
    from shell_local_stt import LocalSTTConfig, SherpaOnnxStreamingSTT

    cfg = LocalSTTConfig.from_environment()
    assert cfg.configured_kind() == "whisper"
    assert cfg.missing_reason() == ""

    stt = SherpaOnnxStreamingSTT.from_environment()
    result = stt.transcribe(np.ones(1600, dtype=np.int16), sample_rate=16000)

    assert result.ok is True
    assert result.text == "namaste shell"
    assert result.metadata["offline_model_kind"] == "whisper"
    assert calls["from_whisper"]["language"] == "hi"
    assert calls["from_whisper"]["task"] == "transcribe"


def test_voice_listener_local_stt_helper_emits_latency(monkeypatch):
    import numpy as np
    from shell_local_stt import LocalSTTResult
    from shell_voice_listener_runtime import VoiceListenerThread

    class FakeConfig:
        provider = "cpu"

        @staticmethod
        def configured_kind():
            return "transducer"

    class FakeLocalSTT:
        load_ms = 1.0
        config = FakeConfig()

        def transcribe(self, _audio_data, sample_rate):
            return LocalSTTResult(True, "open notepad", elapsed_ms=2.0, metadata={"sample_rate": sample_rate})

    listener = VoiceListenerThread()
    listener._local_stt_enabled = True
    listener._local_stt = FakeLocalSTT()
    events = []
    listener.latency_event.connect(lambda event, payload: events.append((event, payload)))

    text = listener._recognize_with_local_stt(
        np.zeros(1600, dtype=np.int16),
        time.perf_counter(),
        reason="api_error_fallback",
    )

    assert text == "open notepad"
    assert any(event == "local_stt_done" for event, _payload in events)


def test_voice_listener_uses_bundled_local_stt_as_primary(monkeypatch):
    monkeypatch.delenv("SHELL_LOCAL_STT_ENABLED", raising=False)
    monkeypatch.delenv("SHELL_LOCAL_STT_PRIMARY", raising=False)
    import shell_local_stt
    from shell_voice_listener_runtime import VoiceListenerThread

    monkeypatch.setattr(shell_local_stt, "default_local_stt_model_dir", lambda: object())

    listener = VoiceListenerThread()

    assert listener._local_stt_enabled is True
    assert listener._local_stt_primary is True


def test_tool_catalog_discovers_local_stt_status_tool():
    from shell_tool_catalog import discover_tool_catalog

    ids = {item["id"] for item in discover_tool_catalog()}
    assert "shell_local_stt:local_stt_status_tool" in ids
