from pathlib import Path

from core.config import ConfigProfile, build_effective_config, validate_environment


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="replace")


def test_enterprise_config_profiles_are_safe_and_redacted():
    cfg = build_effective_config({
        "SHELL_CONFIG_PROFILE": "enterprise",
        "GOOGLE_API_KEY": "demo-google-key-secret-value",
        "SHELL_PLUGIN_REQUIRE_SIGNATURES": "1",
    })
    redacted = cfg.redacted()
    assert cfg.profile == ConfigProfile.ENTERPRISE
    assert cfg.get_bool("SHELL_PLUGIN_REQUIRE_SIGNATURES") is True
    assert redacted["values"]["GOOGLE_API_KEY"] != "demo-google-key-secret-value"
    assert "****" in redacted["values"]["GOOGLE_API_KEY"]


def test_config_validation_blocks_beginner_risky_flags():
    report = validate_environment({
        "SHELL_CONFIG_PROFILE": "beginner",
        "SHELL_ALLOW_TERMINAL_EXEC": "1",
    })
    data = report.to_dict()
    assert data["status"] == "fail"
    assert any(issue["key"] == "SHELL_ALLOW_TERMINAL_EXEC" for issue in data["issues"])


def test_config_validation_requires_telegram_allowlist_for_remote_control():
    report = validate_environment({
        "SHELL_CONFIG_PROFILE": "advanced",
        "SHELL_TELEGRAM_REMOTE_CONTROL_ENABLED": "1",
    })
    data = report.to_dict()
    assert data["status"] == "fail"
    assert any(issue["key"] == "SHELL_TELEGRAM_ALLOWED_CHAT_IDS" for issue in data["issues"])


def test_phase5_enterprise_docs_exist_and_are_linked():
    docs = [
        "docs/ENTERPRISE_ARCHITECTURE_REVIEW.md",
        "docs/AI_INFRASTRUCTURE_PLAN.md",
        "docs/CONFIGURATION_SYSTEM.md",
        "docs/OBSERVABILITY_AND_DEBUGGING.md",
        "docs/PERFORMANCE_ENGINEERING_PLAN.md",
        "docs/DEVELOPER_EXPERIENCE.md",
        "docs/ENTERPRISE_SECURITY_PREP.md",
        "docs/MONETIZATION_READINESS.md",
        "docs/LONG_TERM_ECOSYSTEM_STRATEGY.md",
    ]
    for path in docs:
        assert (ROOT / path).exists(), path
        assert path.split("/", 1)[1] in _read("docs/README.md")
    readme = _read("README.md")
    assert "docs/ENTERPRISE_ARCHITECTURE_REVIEW.md" in readme
    assert "docs/AI_INFRASTRUCTURE_PLAN.md" in readme
    assert "docs/CONFIGURATION_SYSTEM.md" in readme


def test_enterprise_diagnostics_tools_and_workflows_are_wired():
    assert (ROOT / "tools/config_diagnostics.py").exists()
    assert (ROOT / "tools/enterprise_diagnostics.py").exists()
    ci = _read(".github/workflows/ci.yml")
    release = _read(".github/workflows/release.yml")
    assert "tools/config_diagnostics.py --fail-on-error" in ci
    assert "tools/enterprise_diagnostics.py --fail-on-attention" in ci
    assert "tools/config_diagnostics.py --fail-on-error" in release
    assert "tools/enterprise_diagnostics.py --fail-on-attention" in release


def test_enterprise_docs_reference_real_security_standards():
    security = _read("docs/ENTERPRISE_SECURITY_PREP.md")
    observability = _read("docs/OBSERVABILITY_AND_DEBUGGING.md")
    assert "SLSA" in security
    assert "SBOM" in security
    assert "OpenSSF Scorecard" in security
    assert "OpenTelemetry" in observability
