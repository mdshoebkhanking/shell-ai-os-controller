from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="replace")


def test_apache_license_files_present():
    assert "Apache License" in _read("LICENSE")
    assert "Version 2.0" in _read("LICENSE")
    assert "Copyright 2026 mdshoebking" in _read("NOTICE")
    assert "Apache-2.0" in _read("LEGAL.md")
    assert "Apache-2.0" in _read("THIRD_PARTY_NOTICES.md")


def test_readme_and_package_metadata_use_apache_2():
    assert "Apache License 2.0" in _read("README.md")
    assert "License: MIT" not in _read("README.md")
    assert '"license": "Apache-2.0"' in _read("package.json")


def test_security_policy_warns_against_secret_commits():
    security = _read("SECURITY.md")
    for item in [".env", "API keys", "Telegram bot tokens", ".telegram_*.json"]:
        assert item in security
