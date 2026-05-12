from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8", errors="replace")


def test_phase4_product_ecosystem_docs_exist():
    required = [
        "DESIGN.md",
        "docs/PRODUCT_EXPERIENCE.md",
        "docs/WEBSITE_PLAN.md",
        "docs/PUBLIC_LAUNCH_PLAN.md",
        "docs/ECOSYSTEM_ROADMAP.md",
        "docs/TRUST_AND_CREDIBILITY.md",
        "assets/brand/shell-official-logo.png",
        "banners/social-preview-concept.svg",
    ]
    for path in required:
        assert (ROOT / path).exists(), path


def test_public_docs_link_phase4_experience_assets():
    readme = _read("README.md")
    docs_index = _read("docs/README.md")
    public_release = _read("PUBLIC_RELEASE.md")
    for text in (readme, docs_index, public_release):
        assert "docs/PRODUCT_EXPERIENCE.md" in text or "PRODUCT_EXPERIENCE.md" in text
        assert "docs/PUBLIC_LAUNCH_PLAN.md" in text or "PUBLIC_LAUNCH_PLAN.md" in text
    assert "DESIGN.md" in readme
    assert "docs/TRUST_AND_CREDIBILITY.md" in readme


def test_brand_system_has_real_tokens_and_claim_boundaries():
    design = _read("DESIGN.md")
    trust = _read("docs/TRUST_AND_CREDIBILITY.md")
    for token in ["#18D7F3", "#38D996", "#F4B860", "#FF6673"]:
        assert token in design
    assert "Control your workspace with AI, safely." in design
    assert "Do not say" in design
    assert "Claim Levels" in trust
    assert "Verified" in trust
    assert "Conditional" in trust


def test_product_positioning_is_consistent_and_not_deceptive():
    public_text = "\n".join(
        [
            _read("README.md"),
            _read("github-profile/README.md"),
            _read("docs/PUBLIC_LAUNCH_PLAN.md"),
        ]
    ).lower()
    assert "desktop control layer" in public_text
    assert "human-controlled" in public_text
    for forbidden in [
        "fully autonomous operating system",
        "can do anything",
        "guaranteed to control every app",
    ]:
        assert forbidden not in public_text


def test_first_launch_onboarding_copy_sets_safe_expectations():
    onboarding = _read("shell_ui/onboarding_tour.py")
    assert "AI desktop control layer" in onboarding
    assert "ready tools only when the route is safe" in onboarding
    assert "health checks, repair tools, API setup" in onboarding
    assert "326+ tools" not in onboarding
    assert "anything" not in onboarding
