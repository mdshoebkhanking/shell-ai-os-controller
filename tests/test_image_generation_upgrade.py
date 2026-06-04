import base64

import pytest


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


def test_openai_model_size_mapping_is_provider_safe():
    import shell_image_ai as img

    assert img._openai_size_for_model("dall-e-3", 3840, 2160) == "1792x1024"
    assert img._openai_size_for_model("gpt-image-1", 3840, 2160) == "1536x1024"
    assert img._openai_size_for_model("gpt-image-1", 1080, 1920) == "1024x1536"
    assert img._openai_size_for_model("gpt-image-2", 1921, 1081).endswith("x1088")


def test_valid_image_bytes_rejects_error_payloads():
    import shell_image_ai as img

    assert img._valid_image_bytes(b"<html>provider error</html>")[0] is False
    assert img._valid_image_bytes(b'{"error":"bad key"}')[0] is False
    assert img._valid_image_bytes(PNG_1X1)[0] is True


@pytest.mark.asyncio
async def test_generate_image_uses_real_provider_routing_and_saves_valid_file(monkeypatch, tmp_path):
    import shell_image_ai as img

    calls = []

    class BadProvider(img.ImageProvider):
        def __init__(self):
            super().__init__("Bad")

        async def generate(self, prompt, width, height, **kwargs):
            calls.append(("bad", width, height))
            return b"<html>not an image</html>"

    class GoodProvider(img.ImageProvider):
        def __init__(self):
            super().__init__("Good")

        def prepare_dimensions(self, width, height):
            return 1536, 864

        async def generate(self, prompt, width, height, **kwargs):
            calls.append(("good", width, height))
            return PNG_1X1

    class DummyHistory:
        def __init__(self):
            self.entries = []

        def add_entry(self, request, result):
            self.entries.append((request, result))

    monkeypatch.setattr(img, "_build_providers", lambda: [BadProvider(), GoodProvider()])
    monkeypatch.setattr(img.Config, "IMAGE_AUTO_OPEN", False)
    monkeypatch.setattr(img.os.path, "expanduser", lambda _p: str(tmp_path))
    monkeypatch.setattr(img, "cache", img.AdvancedCache(str(tmp_path / "cache")))
    monkeypatch.setattr(img, "history", DummyHistory())
    img.rate_limiter.reset()

    result = await img.generate_image_tool.__wrapped__(
        "beautiful realistic mountain photo",
        device_type="4k",
        style="photorealistic",
        use_ai_enhancement=False,
        quality="ultimate",
    )

    assert "✅ **Image Generated!**" in result
    assert "Provider:** Good" in result
    assert "fail Bad" in result
    assert ("good", 1536, 864) in calls
    saved = result.split("`")[1]
    assert (tmp_path / "Pictures" / "Shell_Generated").exists()
    assert img._valid_image_bytes(open(saved, "rb").read())[0] is True


@pytest.mark.asyncio
async def test_generate_image_failure_reports_provider_attempts(monkeypatch, tmp_path):
    import shell_image_ai as img

    class Unavailable(img.ImageProvider):
        def __init__(self):
            super().__init__("Unavailable")

        def is_available(self):
            return False, "missing key"

    monkeypatch.setattr(img, "_build_providers", lambda: [Unavailable()])
    monkeypatch.setattr(img, "cache", img.AdvancedCache(str(tmp_path / "cache")))
    monkeypatch.setattr(img.Config, "IMAGE_LOCAL_FALLBACK", False)
    img.rate_limiter.reset()

    result = await img.generate_image_tool.__wrapped__(
        "clean product photo",
        use_ai_enhancement=False,
    )

    assert "Image generation failed" in result
    assert "skip Unavailable: missing key" in result


@pytest.mark.asyncio
async def test_generate_image_uses_local_preview_when_cloud_providers_fail(monkeypatch, tmp_path):
    import shell_image_ai as img

    class EmptyProvider(img.ImageProvider):
        def __init__(self):
            super().__init__("Empty")

        async def generate(self, prompt, width, height, **kwargs):
            return b""

    monkeypatch.setattr(img, "_build_providers", lambda: [EmptyProvider()])
    monkeypatch.setattr(img.Config, "IMAGE_LOCAL_FALLBACK", True)
    monkeypatch.setattr(img.Config, "IMAGE_AUTO_OPEN", False)
    monkeypatch.setattr(img.os.path, "expanduser", lambda _p: str(tmp_path))
    monkeypatch.setattr(img, "cache", img.AdvancedCache(str(tmp_path / "cache")))
    img.rate_limiter.reset()

    result = await img.generate_image_tool.__wrapped__(
        "clean product photo",
        use_ai_enhancement=False,
    )

    assert "✅ **Image Generated!**" in result
    assert "Provider:** Shell Local Preview" in result
    saved = result.split("`")[1]
    assert img._valid_image_bytes(open(saved, "rb").read())[0] is True
