import asyncio


def test_evolution_governor_creates_a_proposal_without_code_write(monkeypatch, tmp_path):
    from core.evolution import EvolutionGovernor

    monkeypatch.delenv("SHELL_ALLOW_CODE_WRITE", raising=False)
    governor = EvolutionGovernor(tmp_path / "proposals.json")

    proposal = governor.propose("Add a safe text cleanup tool", target_scope="new_tool")
    status = governor.status()

    assert proposal.status == "pending_approval"
    assert proposal.governance["requires_approval"] is True
    assert status["code_write_enabled"] is False
    assert (tmp_path / "proposals.json").exists()


def test_evolution_governor_approval_only_updates_metadata(tmp_path):
    from core.evolution import EvolutionGovernor

    governor = EvolutionGovernor(tmp_path / "proposals.json")
    proposal = governor.propose("Fix a UI spacing issue", target_scope="ui_fix")
    approved = governor.approve(proposal.proposal_id, approved_by="test-user")

    assert approved.status == "approved"
    assert approved.approved_by == "test-user"
    assert not (tmp_path / "shell_new_tool.py").exists()


def test_evolution_patch_validation_blocks_unsafe_code(tmp_path):
    from core.evolution import EvolutionGovernor

    governor = EvolutionGovernor(tmp_path / "proposals.json")
    validation = governor.validate_patch(
        "shell_bad.py",
        "import os\n\nasync def bad_tool() -> str:\n    os.system('rm -rf /')\n    return 'bad'\n",
    )

    assert validation.ok is False
    assert any("shell execution" in item for item in validation.blockers)


def test_evolution_patch_validation_accepts_safe_tool(tmp_path):
    from core.evolution import EvolutionGovernor

    governor = EvolutionGovernor(tmp_path / "proposals.json")
    validation = governor.validate_patch(
        "shell_text_cleanup.py",
        "from shell_safe_executor import god_tier_tool as function_tool\n\n"
        "@function_tool\n"
        "async def text_cleanup_tool(text: str) -> str:\n"
        "    return ' '.join(str(text).split())\n",
    )

    assert validation.ok is True
    assert "text_cleanup_tool" in validation.functions


def test_evolution_tools_are_read_only_until_gated_write(monkeypatch, tmp_path):
    monkeypatch.setenv("SHELL_EVOLUTION_PROPOSALS_PATH", str(tmp_path / "proposals.json"))
    monkeypatch.delenv("SHELL_ALLOW_CODE_WRITE", raising=False)

    from shell_evolution import evolution_governor_status_tool, propose_evolution_tool, validate_evolution_patch_tool

    proposal_report = asyncio.run(propose_evolution_tool("Add a tiny text cleanup tool", "new_tool"))
    validation_report = asyncio.run(
        validate_evolution_patch_tool(
            "shell_text_cleanup.py",
            "from shell_safe_executor import god_tier_tool as function_tool\n\n"
            "@function_tool\n"
            "async def text_cleanup_tool(text: str) -> str:\n"
            "    return ' '.join(str(text).split())\n",
        )
    )
    status_report = asyncio.run(evolution_governor_status_tool())

    assert "EVOLUTION PROPOSAL CREATED" in proposal_report
    assert "Status: PASS" in validation_report
    assert "Code write enabled: False" in status_report
    assert not (tmp_path / "shell_text_cleanup.py").exists()
