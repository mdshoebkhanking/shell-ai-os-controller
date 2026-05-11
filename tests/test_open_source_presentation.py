from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="replace")


def test_premium_readme_sections_exist():
    readme = _read("README.md")
    for section in [
        "## Feature Highlights",
        "## Screenshots",
        "## Demo Media",
        "## Architecture",
        "## Beginner Install",
        "## Troubleshooting",
        "## FAQ",
        "## Roadmap",
        "## Contributing",
    ]:
        assert section in readme
    assert "banners/shell-ai-os-controller-banner.svg" in readme
    assert "docs/INSTALL_BEGINNER.md" in readme


def test_github_community_files_exist():
    required = [
        ".github/workflows/ci.yml",
        ".github/workflows/security.yml",
        ".github/workflows/release.yml",
        ".github/workflows/repo-audit.yml",
        ".github/dependabot.yml",
        ".github/CODEOWNERS",
        ".github/labels.yml",
        ".github/ISSUE_TEMPLATE/config.yml",
        ".github/ISSUE_TEMPLATE/bug_report.yml",
        ".github/ISSUE_TEMPLATE/feature_request.yml",
        ".github/ISSUE_TEMPLATE/voice_ui_bug.yml",
        ".github/PULL_REQUEST_TEMPLATE.md",
        ".github/RELEASE_TEMPLATE.md",
        "CONTRIBUTING.md",
        "CODE_OF_CONDUCT.md",
        "requirements-ci.txt",
        ".editorconfig",
        ".gitattributes",
    ]
    for path in required:
        assert (ROOT / path).exists(), path


def test_media_placeholders_exist():
    required = [
        "banners/shell-ai-os-controller-banner.svg",
        "screenshots/add-chat-screenshot.svg",
        "screenshots/add-voice-screenshot.svg",
        "screenshots/add-tools-screenshot.svg",
        "screenshots/add-settings-screenshot.svg",
        "gifs/add-setup-demo.svg",
        "videos/add-video-demo.svg",
    ]
    for path in required:
        assert (ROOT / path).exists(), path


def test_profile_strategy_and_readme_exist():
    profile = _read("github-profile/README.md")
    strategy = _read("docs/GITHUB_PROFILE_STRATEGY.md")
    assert "AI Developer" in profile
    assert "Open Source Builder" in profile
    assert "Automation Engineer" in profile
    assert "mdshoebking" in strategy
    assert "Pinned Repository Plan" in strategy


def test_documentation_ecosystem_exists():
    docs = [
        "docs/README.md",
        "docs/DEVELOPER_GUIDE.md",
        "docs/ARCHITECTURE_GUIDE.md",
        "docs/API_GUIDE.md",
        "docs/TROUBLESHOOTING.md",
        "docs/FAQ.md",
        "docs/ADVANCED_USAGE.md",
        "docs/ROADMAP.md",
        "docs/COMMUNITY.md",
        "docs/RELEASE_PROCESS.md",
        "docs/BRANCHING_STRATEGY.md",
    ]
    for path in docs:
        assert (ROOT / path).exists(), path


def test_ci_workflows_use_current_action_families():
    ci = _read(".github/workflows/ci.yml")
    security = _read(".github/workflows/security.yml")
    release = _read(".github/workflows/release.yml")
    assert "actions/checkout@v6" in ci
    assert "actions/setup-python@v6" in ci
    assert "actions/upload-artifact@v7" in ci
    assert "github/codeql-action/init@v4" in security
    assert "actions/dependency-review-action@v4" in security
    assert "actions/attest@v4" in release
    assert "tools/package_public_release.py" in release
