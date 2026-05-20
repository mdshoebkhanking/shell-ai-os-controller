from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from . import __version__
from .agent_loop import create_user_request, run_agent_task
from .config import ShellAIConfig
from .observability import TRACE_STORE


def _print_json(payload: object) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="shellai", description="Shell AI OS controller CLI")
    parser.add_argument("--version", action="version", version=f"shellai {__version__}")
    sub = parser.add_subparsers(dest="command")

    run = sub.add_parser("run", help="Handle a one-shot natural-language or explicit shell request")
    run.add_argument("prompt", nargs="+", help="User request. Prefix shell commands with shell:, !, or $.")
    run.add_argument("--json", action="store_true", help="Print full JSON response")

    sub.add_parser("chat", help="Start an interactive terminal session")
    sub.add_parser("doctor", help="Diagnose local shellai configuration")

    daemon = sub.add_parser("daemon", help="Manage the background daemon")
    daemon_sub = daemon.add_subparsers(dest="daemon_command")
    daemon_sub.add_parser("start")
    daemon_sub.add_parser("stop")
    daemon_sub.add_parser("status")
    daemon_enqueue = daemon_sub.add_parser("enqueue")
    daemon_enqueue.add_argument("prompt", nargs="+")
    daemon_process = daemon_sub.add_parser("process")
    daemon_process.add_argument("--limit", type=int, default=10)

    tools = sub.add_parser("tools", help="List or manage tool switches")
    tools.add_argument("tool_command", nargs="?", default="list", choices=["list"])

    model = sub.add_parser("model", help="Show or set model configuration")
    model_sub = model.add_subparsers(dest="model_command")
    model_sub.add_parser("show")
    model_set = model_sub.add_parser("set")
    model_set.add_argument("role", choices=["planning", "command", "summarization"])
    model_set.add_argument("model")

    config = sub.add_parser("config", help="Show or set shellai config values")
    config_sub = config.add_subparsers(dest="config_command")
    config_sub.add_parser("get")
    config_set = config_sub.add_parser("set")
    config_set.add_argument("key")
    config_set.add_argument("value")

    skills = sub.add_parser("skills", help="Manage learned skills")
    skills.add_argument("skills_command", nargs="?", default="list", choices=["list", "show", "create", "edit", "remove"])
    skills.add_argument("skill_id", nargs="?", help="Skill id or name for commands like show")

    trace = sub.add_parser("trace", help="Inspect in-memory request traces for this process")
    trace_sub = trace.add_subparsers(dest="trace_command")
    trace_list = trace_sub.add_parser("list")
    trace_list.add_argument("--limit", type=int, default=10)

    monitor = sub.add_parser("monitor", help="Inspect persisted ShellAI request traces")
    monitor.add_argument("--limit", type=int, default=20)
    monitor.add_argument("--errors", action="store_true", help="Show only error traces")
    monitor.add_argument("--blocked", action="store_true", help="Show only blocked traces")

    sub.add_parser("optimize", help="Show read-only ShellAI optimizer suggestions")

    cron = sub.add_parser("cron", help="Run manual maintenance jobs")
    cron_sub = cron.add_subparsers(dest="cron_command")
    cron_sub.add_parser("list")
    cron_run = cron_sub.add_parser("run")
    cron_run.add_argument("job")
    cron_run.add_argument("--dry-run", action="store_true")

    return parser


def _handle_run(args: argparse.Namespace) -> int:
    request = create_user_request(" ".join(args.prompt))
    response = run_agent_task(request)
    if args.json:
        _print_json(response)
    else:
        print(response.get("summary") or response.get("message") or "")
        print(f"status: {response['status']}")
        print(f"trace: {response['trace_id']}")
        for step in response.get("steps", []):
            detail = step.get("metadata", {}).get("command") or step.get("description", "")
            print(f"- {step.get('tool')} {step.get('status')}: {detail}")
            if step.get("stderr"):
                print(f"  {step['stderr']}")
    return 0


def _handle_chat() -> int:
    print("shellai chat (Stage 1). Type 'exit' to quit.")
    while True:
        try:
            line = input("shellai> ")
        except EOFError:
            print()
            return 0
        if line.strip().lower() in {"exit", "quit"}:
            return 0
        if not line.strip():
            continue
        response = run_agent_task(create_user_request(line))
        print(response.get("summary") or response.get("message") or "")
        print(f"[{response['status']}] trace={response['trace_id']}")


def _handle_doctor() -> int:
    config = ShellAIConfig.load()
    from .models import ModelRouter

    router = ModelRouter(config)
    from .policy import policy_diagnostics

    payload = {
        "status": "ok",
        "version": __version__,
        **config.diagnostics(),
        "model_router": router.diagnostics(),
        "risk_policy_default": config.risk_policy.get("default", "ASK"),
        "policy": policy_diagnostics(config),
    }
    _print_json(payload)
    return 0


def _handle_config(args: argparse.Namespace) -> int:
    config = ShellAIConfig.load()
    if args.config_command in {None, "get"}:
        _print_json(config.to_dict())
        return 0
    config.set_value(args.key, args.value)
    config.save()
    print(f"set {args.key}")
    return 0


def _handle_model(args: argparse.Namespace) -> int:
    config = ShellAIConfig.load()
    if args.model_command in {None, "show"}:
        _print_json({"provider": config.provider, "models": config.models.to_dict()})
        return 0
    config.set_value(f"models.{args.role}", args.model)
    config.save()
    print(f"set models.{args.role}")
    return 0


def _handle_trace(args: argparse.Namespace) -> int:
    traces = [trace.to_dict() for trace in TRACE_STORE.recent(args.limit)]
    _print_json({"traces": traces})
    return 0


def _handle_monitor(args: argparse.Namespace) -> int:
    from .monitor import compact_trace_rows, list_trace_snapshots

    config = ShellAIConfig.load()
    status_filter = ""
    if args.errors:
        status_filter = "error"
    if args.blocked:
        status_filter = "blocked"
    rows = list_trace_snapshots(config, limit=args.limit, status_filter=status_filter)
    _print_json({"traces": compact_trace_rows(rows)})
    return 0


def _handle_optimize() -> int:
    from .agents_optimizer import OptimizerAgent

    config = ShellAIConfig.load()
    agent = OptimizerAgent(config=config)
    _print_json(agent.generate_report())
    return 0


def _handle_cron(args: argparse.Namespace) -> int:
    from .cron import list_jobs, run_job

    if args.cron_command in {None, "list"}:
        _print_json({"jobs": list_jobs()})
        return 0
    result = run_job(args.job, dry_run=args.dry_run)
    _print_json(result)
    return 0


def _handle_daemon(args: argparse.Namespace) -> int:
    from .daemon import ShellAIDaemon

    daemon = ShellAIDaemon()
    selected = args.daemon_command or "status"
    if selected == "start":
        _print_json(daemon.start())
        return 0
    if selected == "stop":
        _print_json(daemon.stop())
        return 0
    if selected == "enqueue":
        _print_json({"task": daemon.enqueue_task(" ".join(args.prompt))})
        return 0
    if selected == "process":
        _print_json({"processed": daemon.process_all(limit=args.limit), "status": daemon.status()})
        return 0
    _print_json(daemon.status())
    return 0


def _handle_skills(args: argparse.Namespace) -> int:
    from .skills import SkillManager

    try:
        manager = SkillManager()
    except PermissionError as exc:
        _print_json({
            "error": "skill storage is not writable",
            "message": str(exc),
            "hint": "Set SHELLAI_CONFIG to a writable config path or run setup on a writable home directory.",
        })
        return 1
    if args.skills_command == "list":
        _print_json({"skills": manager.list_skills()})
        return 0
    if args.skills_command == "show":
        if not args.skill_id:
            print("skills show requires a skill id", file=sys.stderr)
            return 2
        skill = manager.get_skill_by_id(args.skill_id)
        if skill is None:
            print(f"skill not found: {args.skill_id}", file=sys.stderr)
            return 1
        _print_json(skill.to_dict(include_source_path=True))
        return 0
    print(f"skills {args.skills_command}: not implemented yet")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command

    if command == "run":
        return _handle_run(args)
    if command == "chat":
        return _handle_chat()
    if command == "doctor":
        return _handle_doctor()
    if command == "config":
        return _handle_config(args)
    if command == "model":
        return _handle_model(args)
    if command == "trace":
        return _handle_trace(args)
    if command == "monitor":
        return _handle_monitor(args)
    if command == "optimize":
        return _handle_optimize()
    if command == "cron":
        return _handle_cron(args)
    if command == "daemon":
        return _handle_daemon(args)
    if command == "tools":
        config = ShellAIConfig.load()
        _print_json({"enabled_tools": config.enabled_tools})
        return 0
    if command == "skills":
        return _handle_skills(args)

    parser.print_help(sys.stderr)
    return 2


__all__ = ["build_parser", "main"]
