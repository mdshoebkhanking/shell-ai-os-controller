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
