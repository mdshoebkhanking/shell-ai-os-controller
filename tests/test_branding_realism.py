from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8", errors="replace")


def test_visible_version_is_stable_release_semver():
    assert re.fullmatch(r"1\.0\.\d+", _read("VERSION").strip())

    visible_files = [
        "shell_ui/shell_cinematic_full.py",
        "shell_ui/splash_screen.py",
        "README.md",
        "PUBLIC_RELEASE.md",
        "CHANGELOG.md",
    ]
    joined = "\n".join(_read(path) for path in visible_files)

    assert ("1.0.0" + "-rc.1") not in joined
    assert ("v" + "10.0") not in joined
    assert "v10" not in joined


def test_creator_credit_is_visible_and_hardcoded():
    visible_files = [
        "shell_ui/shell_cinematic_full.py",
        "shell_ui/splash_screen.py",
        "shell_telegram.py",
        "agent.py",
        "shell_prompts.py",
        "README.md",
        "PUBLIC_RELEASE.md",
    ]

    for path in visible_files:
        assert "mdshoebking" in _read(path), path


def test_hype_phrases_removed_from_user_visible_surfaces():
    visible_files = [
        "shell_ui/shell_cinematic_full.py",
        "shell_ui/splash_screen.py",
        "shell_safe_executor.py",
        "agent.py",
        "shell_telegram.py",
        "shell_prompts.py",
        "shell_system_god.py",
        "shell_brain/god_mode.py",
        "shell_brain/__init__.py",
        "README.md",
        "INSTALLATION.md",
    ]
    banned = [
        "God-Tier" + " Execution",
        "GOD MODE" + " ACTIVATED",
        "World's Most" + " Powerful",
        "world's most" + " powerful",
        "Unlimited" + " Power",
        "Level " + "1000000",
        "Level " + "10000",
        "Ultra Pro" + " Max",
    ]
    joined = "\n".join(_read(path) for path in visible_files)

    for phrase in banned:
        assert phrase not in joined


def test_prompt_surfaces_use_grounded_addressing():
    joined = "\n".join(
        _read(path)
        for path in [
            "shell_prompts.py",
            "shell_voice.py",
            "shell_ui/shell_cinematic_full.py",
            "agent.py",
        ]
    )

    assert "created by mdshoebking" in joined.lower()
    assert "Default addressing: 'Master'" not in joined
    assert "STATUS: ONLINE" not in joined
