from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


CORE_AGENT_COMMANDS: list[tuple[str, str]] = [
    ("DeveloperAgent", '/agent shell_agents:developer_agent_tool {"task":"UI smoke test only: reply in one short sentence that DeveloperAgent is ready. Do not write files."}'),
    ("WebsiteBuilderAgent", '/agent shell_agents:website_builder_agent_tool {"task":"UI smoke test only: suggest one tiny homepage section in one sentence."}'),
    ("AppBuilderAgent", '/agent shell_agents:app_builder_agent_tool {"task":"UI smoke test only: name one safe app feature in one sentence. Do not create files."}'),
    ("APIAgent", '/agent shell_agents:api_agent_tool {"task":"UI smoke test only: propose one REST endpoint in one sentence."}'),
    ("DatabaseAgent", '/agent shell_agents:database_agent_tool {"task":"UI smoke test only: propose one table name in one sentence."}'),
    ("SystemAgent", '/agent shell_agents:system_agent_tool {"task":"UI smoke test only: mention one safe system diagnostic in one sentence. Do not run commands."}'),
    ("SocialAgent", '/agent shell_agents:social_agent_tool {"task":"UI smoke test only: draft one short friendly social reply. Do not send anything."}'),
    ("SecurityAgent", '/agent shell_agents:security_agent_tool {"task":"UI smoke test only: name one safe security check in one sentence. Do not scan."}'),
    ("ResearchAgent", '/agent shell_agents:research_agent_tool {"task":"UI smoke test only: give one research question in one sentence. Do not browse."}'),
    ("FileAgent", '/agent shell_agents:file_agent_tool {"task":"UI smoke test only: suggest one safe file organization step. Do not touch files."}'),
    ("CreativeAgent", '/agent shell_agents:creative_agent_tool {"task":"UI smoke test only: give one short brand tagline."}'),
    ("ProductivityAgent", '/agent shell_agents:productivity_agent_tool {"task":"UI smoke test only: give one short productivity tip."}'),
    ("DataAgent", '/agent shell_agents:data_agent_tool {"task":"UI smoke test only: suggest one metric to chart in one sentence."}'),
    ("NetworkAgent", '/agent shell_agents:network_agent_tool {"task":"UI smoke test only: name one safe network diagnostic. Do not scan."}'),
    ("DevOpsAgent", '/agent shell_agents:devops_agent_tool {"task":"UI smoke test only: name one deployment checklist item. Do not deploy."}'),
    ("BrowserAgent", '/agent shell_agents:browser_agent_tool {"task":"UI smoke test only: name one browser QA action. Do not open browser."}'),
    ("CommunicationAgent", '/agent shell_agents:communication_agent_tool {"task":"UI smoke test only: write one short meeting reminder. Do not send."}'),
    ("LearningAgent", '/agent shell_agents:learning_agent_tool {"task":"UI smoke test only: explain loops in one sentence."}'),
    ("AutomationAgent", '/agent shell_agents:automation_agent_tool {"task":"UI smoke test only: suggest one safe automation idea. Do not execute."}'),
    ("TestingAgent", '/agent shell_agents:testing_agent_tool {"task":"UI smoke test only: name one UI test case in one sentence."}'),
    ("MasterAgent", '/agent shell_agents:master_agent_tool {"task":"UI smoke test only: route this harmless status check and reply one sentence. Do not execute tools."}'),
]


EXTRA_AGENT_COMMANDS: list[tuple[str, str]] = [
    ("FinanceAgent", '/agent shell_extra_agents:finance_agent_tool {"query":"UI smoke test only: give one short budgeting tip, no advice."}'),
    ("LegalAgent", '/agent shell_extra_agents:legal_agent_tool {"query":"UI smoke test only: explain NDA in one sentence, not legal advice."}'),
    ("HealthAgent", '/agent shell_extra_agents:health_agent_tool {"query":"UI smoke test only: give one general hydration tip, no diagnosis."}'),
    ("CookingAgent", '/agent shell_extra_agents:cooking_agent_tool {"query":"UI smoke test only: suggest one simple breakfast idea."}'),
    ("TravelAgent", '/agent shell_extra_agents:travel_agent_tool {"query":"UI smoke test only: give one packing tip."}'),
    ("StudyAgent", '/agent shell_extra_agents:study_agent_tool {"query":"UI smoke test only: give one exam study tip."}'),
    ("LanguageTutorAgent", '/agent shell_extra_agents:language_tutor_agent_tool {"query":"UI smoke test only: translate hello to Hindi and keep it short."}'),
    ("ResumeAgent", '/agent shell_extra_agents:resume_agent_tool {"query":"UI smoke test only: improve one resume bullet in one sentence."}'),
    ("InterviewAgent", '/agent shell_extra_agents:interview_agent_tool {"query":"UI smoke test only: ask one common interview question."}'),
    ("MarketingAgent", '/agent shell_extra_agents:marketing_agent_tool {"query":"UI smoke test only: write one short product hook."}'),
    ("SEOAgent", '/agent shell_extra_agents:seo_agent_tool {"query":"UI smoke test only: suggest one SEO keyword idea."}'),
    ("GameDesignAgent", '/agent shell_extra_agents:game_design_agent_tool {"query":"UI smoke test only: suggest one simple game mechanic."}'),
    ("StorytellerAgent", '/agent shell_extra_agents:storyteller_agent_tool {"query":"UI smoke test only: write one tiny story sentence."}'),
    ("PhilosophyAgent", '/agent shell_extra_agents:philosophy_agent_tool {"query":"UI smoke test only: define courage in one sentence."}'),
    ("DebateAgent", '/agent shell_extra_agents:debate_agent_tool {"query":"UI smoke test only: give one argument for reading books."}'),
]


SYSTEM_AGENT_COMMANDS: list[tuple[str, str]] = [
    ("ListAgents", "/agent shell_agents:list_agents_tool {}"),
    ("DeploySwarm", '/agent shell_agent_tools:deploy_swarm_tool {"mission_objective":"UI smoke test only: produce a one-line readiness report. Do not create files, run commands, browse, or modify anything."}'),
]


def _process_events(app, duration_s: float = 0.15) -> None:
    deadline = time.time() + duration_s
    while time.time() < deadline:
        app.processEvents()
        time.sleep(0.01)


def _message_text(window) -> str:
    from PyQt6.QtWidgets import QLabel

    return "\n".join(label.text() for label in window.chat_page.findChildren(QLabel))


def _message_labels(window) -> list[str]:
    from PyQt6.QtWidgets import QLabel

    return [label.text() for label in window.chat_page.findChildren(QLabel)]


def _wait_for_workers(window, app, timeout_s: float) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        app.processEvents()
        workers = list(getattr(window, "_backend_command_workers", []) or [])
        if not any(worker is not None and worker.isRunning() for worker in workers):
            return True
        time.sleep(0.03)
    return False


def _send_chat(window, app, label: str, command: str, timeout_s: float) -> dict[str, object]:
    before_labels = _message_labels(window)
    started = time.perf_counter()
    window.chat_page._input.setPlainText(command)
    _process_events(app, 0.08)
    window.chat_page._send()
    _process_events(app, 0.12)
    workers_done = _wait_for_workers(window, app, timeout_s=timeout_s)
    elapsed_ms = round((time.perf_counter() - started) * 1000.0, 2)
    _process_events(app, 0.35)
    after_labels = _message_labels(window)
    if len(after_labels) >= len(before_labels):
        delta = "\n".join(after_labels[len(before_labels):]).strip()
    else:
        delta = _message_text(window)
    shell_part = delta.rsplit("\nS\nSHELL", 1)[-1] if "\nS\nSHELL" in delta else delta
    lower = shell_part.lower()
    failed = (
        not workers_done
        or re.search(r"\b(failed via|failed:|failed to|all brains failed)\b", lower) is not None
        or "tool is not ready" in lower
        or "traceback" in lower
        or "agent unavailable" in lower
        or "error:" in lower
    )
    return {
        "label": label,
        "command": command,
        "workers_done": workers_done,
        "elapsed_ms": elapsed_ms,
        "ok": not failed,
        "response_tail": delta[-1600:],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Drive all Shell agents through the real chat UI.")
    parser.add_argument("--visible", action="store_true")
    parser.add_argument("--include-swarm", action="store_true")
    parser.add_argument("--timeout-s", type=float, default=95.0)
    parser.add_argument("--json-out", default="/private/tmp/shell_agents_ui_probe_report.json")
    args = parser.parse_args()

    if not args.visible:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("SHELL_V2_TIMEOUT_S", "3")

    try:
        from shell_config import config as _shell_config  # noqa: F401
    except Exception:
        pass

    from PyQt6.QtWidgets import QApplication
    from shell_ui.shell_cinematic_full import ShellHoloUI

    app = QApplication.instance() or QApplication(sys.argv)
    window = ShellHoloUI()
    window.resize(1260, 720)
    window.show()
    _process_events(app, 1.0)
    try:
        window._on_page_change(0)
    except Exception:
        pass

    commands = list(CORE_AGENT_COMMANDS) + list(EXTRA_AGENT_COMMANDS) + [SYSTEM_AGENT_COMMANDS[0]]
    if args.include_swarm:
        commands.append(SYSTEM_AGENT_COMMANDS[1])

    report: dict[str, object] = {
        "ok": True,
        "total": len(commands),
        "passed": 0,
        "failed": 0,
        "results": [],
    }

    try:
        for idx, (label, command) in enumerate(commands, 1):
            print(f"[{idx}/{len(commands)}] {label}", flush=True)
            row = _send_chat(window, app, label, command, timeout_s=args.timeout_s)
            report["results"].append(row)
            if row["ok"]:
                report["passed"] = int(report["passed"]) + 1
            else:
                report["failed"] = int(report["failed"]) + 1
                report["ok"] = False
    except Exception as exc:
        report["ok"] = False
        report.setdefault("errors", []).append(str(exc))
    finally:
        try:
            window._stop_backend_command_workers()
        except Exception:
            pass
        window.close()
        _process_events(app, 0.3)

    Path(args.json_out).write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True), flush=True)
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
