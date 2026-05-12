from __future__ import annotations

import json
import subprocess
import sys


def test_brain_core_import_does_not_load_provider_sdks() -> None:
    code = (
        "import json, os, sys, time; "
        "os.environ['OPENAI_API_KEY']='test-key'; "
        "os.environ['GOOGLE_API_KEY']='test-key'; "
        "started=time.perf_counter(); "
        "import brain.core; "
        "brain=brain.core.MultiAIBrain(); "
        "print(json.dumps({"
        "'import_init_ms': round((time.perf_counter()-started)*1000, 3), "
        "'providers': list(brain.providers.keys()), "
        "'openai_loaded': 'openai' in sys.modules, "
        "'google_genai_loaded': 'google.genai' in sys.modules, "
        "'google_generativeai_loaded': 'google.generativeai' in sys.modules, "
        "'aiohttp_loaded': 'aiohttp' in sys.modules, "
        "'mistral_loaded': 'mistralai.client' in sys.modules, "
        "'openai_provider_loaded': 'brain.providers.openai_p' in sys.modules, "
        "'gemini_provider_loaded': 'brain.providers.gemini_p' in sys.modules, "
        "'groq_provider_loaded': 'brain.providers.groq_p' in sys.modules"
        "}))"
    )

    proc = subprocess.run(
        [sys.executable, "-c", code],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=20,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr[-1200:]
    data = json.loads(proc.stdout.strip().splitlines()[-1])
    assert "openai" in data["providers"]
    assert "gemini" in data["providers"]
    assert data["openai_loaded"] is False
    assert data["google_genai_loaded"] is False
    assert data["google_generativeai_loaded"] is False
    assert data["aiohttp_loaded"] is False
    assert data["mistral_loaded"] is False
    assert data["openai_provider_loaded"] is False
    assert data["gemini_provider_loaded"] is False
    assert data["groq_provider_loaded"] is False


def test_lazy_provider_proxy_loads_only_selected_provider() -> None:
    code = """
import asyncio
import json
import os
import sys

os.environ.pop("GROQ_API_KEY", None)
from brain.core import MultiAIBrain

brain = MultiAIBrain()
before = {
    "groq_provider_loaded": "brain.providers.groq_p" in sys.modules,
    "aiohttp_loaded": "aiohttp" in sys.modules,
}

async def main():
    try:
        await brain.providers["groq"].generate_response_async(messages=[{"role": "user", "content": "hi"}])
    except Exception as exc:
        return str(exc)
    return ""

error = asyncio.run(main())
after = {
    "groq_provider_loaded": "brain.providers.groq_p" in sys.modules,
    "aiohttp_loaded": "aiohttp" in sys.modules,
}
print(json.dumps({
    "before": before,
    "after": after,
    "error": error,
    "diag": brain.get_provider_runtime_diagnostics()["groq"],
}))
"""

    proc = subprocess.run(
        [sys.executable, "-c", code],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=20,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr[-1200:]
    data = json.loads(proc.stdout.strip().splitlines()[-1])
    assert data["before"] == {"groq_provider_loaded": False, "aiohttp_loaded": False}
    assert data["after"]["groq_provider_loaded"] is True
    assert data["after"]["aiohttp_loaded"] is False
    assert "Groq API Key missing" in data["error"]
    assert data["diag"]["loaded"] is True
    assert data["diag"]["load_ms"] is not None
