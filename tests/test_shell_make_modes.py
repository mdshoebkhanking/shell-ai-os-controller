from __future__ import annotations


def test_detect_make_mode_defaults_to_local_basic(monkeypatch):
    from shell_make_modes import TaskMode, detect_make_mode
    from shell_task_mode import CLOUD_PROVIDER_KEY_GROUPS

    for group in CLOUD_PROVIDER_KEY_GROUPS:
        for key in group:
            monkeypatch.delenv(key, raising=False)

    assert detect_make_mode("Make a simple PDF summary") == TaskMode.LOCAL_BASIC


def test_local_make_pdf_summary_is_structured():
    from shell_make_modes import local_make_pdf

    body = local_make_pdf("Daily Notes", "First point. Second point. Third point.", summary=True)

    assert "Daily Notes" in body
    assert "Summary" in body
    assert "- First point." in body


def test_cloud_make_pdf_uses_cloud_output():
    from shell_make_modes import cloud_make_pdf

    body = cloud_make_pdf(
        "Product Spec",
        "rough notes",
        lambda _prompt, _system: "Product Spec\n\nExecutive Summary\n- Pro output",
        summary=True,
    )

    assert "Executive Summary" in body
    assert "Pro output" in body


def test_offline_basic_website_has_five_distinct_layouts():
    from shell_make_modes import local_make_simple_website, offline_basic_website_blueprint

    layouts = [
        offline_basic_website_blueprint("make a website for Shell AI OS controller", variant_index=index)
        for index in range(5)
    ]

    assert len({layout["pattern"] for layout in layouts}) == 5
    html_outputs = [local_make_simple_website("make a website for Shell AI OS controller", variant_index=index) for index in range(5)]
    assert len(set(html_outputs)) == 5
    assert all("make a website for shell ai os controller" not in html.lower() for html in html_outputs)
    assert any("Control" in html or "friction" in html for html in html_outputs)


def test_offline_basic_website_maps_prompt_to_site_type_and_style():
    from shell_make_modes import offline_basic_website_blueprint

    portfolio = offline_basic_website_blueprint("make a minimal portfolio website for a photographer", variant_index=3)
    blog = offline_basic_website_blueprint("create a blog site about product strategy", variant_index=4)

    assert portfolio["meta"]["site_type"] == "portfolio"
    assert blog["meta"]["site_type"] == "blog"
    assert portfolio["css_vars"]
    assert portfolio["html_body"]


def test_cloud_make_advanced_website_is_online_pro_strategy_hook():
    from shell_make_modes import cloud_make_advanced_website

    calls = []

    def fake_cloud(prompt, system):
        calls.append((prompt, system))
        return "{site_type:'saas', pages:['home','pricing'], layout:'bento'}"

    result = cloud_make_advanced_website("top 2026 SaaS website for Shell", fake_cloud)

    assert "pages" in result
    assert "ONLINE_PRO" in calls[0][1]
    assert "Shell" in calls[0][0]


def test_online_pro_website_blueprint_uses_web_context_and_local_pipeline():
    from shell_make_modes import TaskMode, online_pro_website_blueprint

    calls = []

    def fake_cloud(prompt, system):
        calls.append((prompt, system))
        return "{layout:'premium multi-page', copy:'provider refined'}"

    blueprint = online_pro_website_blueprint(
        "really good marketing website for Shell AI",
        fake_cloud,
        fetch_web_context=lambda topic: f"current context for {topic}",
    )

    assert blueprint["mode"] == TaskMode.CLOUD_PRO.value
    assert blueprint["web_context_used"] is True
    assert "current context" in calls[0][0]
    assert blueprint["html_body"]
    assert blueprint["css_vars"]
