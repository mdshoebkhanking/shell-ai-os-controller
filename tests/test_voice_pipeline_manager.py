from shell_voice_pipeline import (
    VADResult,
    VoicePipelineConfig,
    VoicePipelineManager,
    WakeWordResult,
)


class FakeWakeDetector:
    def __init__(self, scores):
        self._scores = list(scores)

    def detect(self, _audio_frame):
        score = self._scores.pop(0) if self._scores else 0.0
        return WakeWordResult(score >= 0.5, score=score, label="hey shell", elapsed_ms=12.0)


class FakeVADDetector:
    def __init__(self, events):
        self._events = list(events)
        self.reset_count = 0

    def process(self, _audio_frame):
        return self._events.pop(0) if self._events else VADResult(elapsed_ms=3.0)

    def reset(self):
        self.reset_count += 1


def test_voice_pipeline_flags_default_off(monkeypatch):
    monkeypatch.delenv("SHELL_WAKE_WORD_ENABLED", raising=False)
    monkeypatch.delenv("SHELL_VAD_ENABLED", raising=False)

    cfg = VoicePipelineConfig.from_environment()

    assert cfg.wake_enabled is False
    assert cfg.vad_enabled is False


def test_wake_word_sensitivity_accepts_percent_env(monkeypatch):
    monkeypatch.setenv("SHELL_WAKE_WORD_SENSITIVITY", "65")

    cfg = VoicePipelineConfig.from_environment()

    assert 0.47 < cfg.wake_threshold < 0.49


def test_manual_trigger_bypasses_wake_gate():
    cfg = VoicePipelineConfig(wake_enabled=True, wake_threshold=0.5)
    manager = VoicePipelineManager(
        cfg,
        wake_detector=FakeWakeDetector([0.0]),
        manual_trigger=True,
    )

    assert manager.state == "armed"
    assert manager.manual_trigger().event == "manual_trigger"


def test_wake_word_detection_activates_under_target_latency():
    cfg = VoicePipelineConfig(wake_enabled=True, wake_threshold=0.5)
    manager = VoicePipelineManager(
        cfg,
        wake_detector=FakeWakeDetector([0.1, 0.92]),
        manual_trigger=False,
    )

    first = manager.process_wake_frame(b"\0" * 160)
    second = manager.process_wake_frame(b"\0" * 160)

    assert first.event == "wake_frame"
    assert second.event == "wake_detected"
    assert second.label == "hey shell"
    assert second.elapsed_ms < 200
    assert second.payload["activation_ms"] < 200
    assert manager.state == "armed"


def test_wake_false_positive_rate_for_noise_frames():
    cfg = VoicePipelineConfig(wake_enabled=True, wake_threshold=0.5)
    manager = VoicePipelineManager(
        cfg,
        wake_detector=FakeWakeDetector([0.05] * 20),
        manual_trigger=False,
    )

    report = manager.false_positive_rate([b"noise"] * 20)

    assert report["frames"] == 20
    assert report["false_positives"] == 0
    assert report["rate"] == 0.0


def test_vad_streaming_start_and_end_events():
    cfg = VoicePipelineConfig(vad_enabled=True)
    vad = FakeVADDetector(
        [
            VADResult(elapsed_ms=2.0),
            VADResult(speech_started=True, elapsed_ms=4.0, raw={"start": 0}),
            VADResult(elapsed_ms=3.0),
            VADResult(speech_ended=True, elapsed_ms=5.0, raw={"end": 1536}),
        ]
    )
    manager = VoicePipelineManager(cfg, vad_detector=vad, manual_trigger=True)

    assert manager.process_vad_frame(b"\0").event == "vad_frame"
    assert manager.process_vad_frame(b"\0").event == "vad_speech_started"
    assert manager.state == "speech"
    assert manager.process_vad_frame(b"\0").event == "vad_frame"
    assert manager.process_vad_frame(b"\0").event == "vad_speech_ended"
    assert manager.state == "processing"


def test_detector_load_failures_degrade_to_button_and_timing_mode():
    def fail(_config):
        raise RuntimeError("dependency missing")

    cfg = VoicePipelineConfig(wake_enabled=True, vad_enabled=True)
    manager = VoicePipelineManager(
        cfg,
        wake_detector_factory=fail,
        vad_detector_factory=fail,
        manual_trigger=False,
    )

    assert manager.state == "armed"
    assert manager.wake_available is False
    assert manager.vad_available is False
    assert len(manager.errors) == 2
