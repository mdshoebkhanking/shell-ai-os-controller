from __future__ import annotations

import argparse
import json
import os
import queue
import re
import sys
import threading
import time
from collections import Counter
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


SAFETY_SKIP_RE = re.compile(
    r"("
    r"delete|remove|cleanup|clean_|clear|reset|wipe|format|kill|shutdown|restart|sleep|lock_pc|system_power|"
    r"terminal|powershell|run_command|execute|python|workflow|hotpatch|self_heal|evolution|"
    r"autopilot|daemon|monitor|install|backup|restore|write|save|create_|add_|remember|learn|"
    r"send_email|send_social|send_telegram|whatsapp|instagram|post|upload|"
    r"desktop_click|desktop_type|desktop_shortcut|mouse|keyboard|brightness|volume|"
    r"download_file|youtube_audio_download"
    r")",
    re.I,
)

ENVIRONMENT_SKIP_RE = re.compile(
    r"("
    r"network_health|ping_host|dns_lookup|check_port|speedtest|stock_|crypto_|latest_news|"
    r"traceroute|trace_route|god_mode|hyper_cortex|omni_brain|"
    r"check_disk_health|disk_health|event_log|resource_hogs|system_diagnostic|scan_system_health|"
    r"browser|youtube|download|scrape|gmail_web|company_email_web|open_url|web_|"
    r"port_scan|net_scan|agent_browser"
    r")",
    re.I,
)


def _make_probe_files(root: Path) -> dict[str, Path]:
    root.mkdir(parents=True, exist_ok=True)
    text = root / "input.txt"
    text.write_text("Shell UI probe sample text\nsecond line\n", encoding="utf-8")
    json_file = root / "sample.json"
    json_file.write_text('{"shell": true, "count": 2}\n', encoding="utf-8")
    csv_file = root / "sample.csv"
    csv_file.write_text("name,value\nalpha,1\nbeta,2\n", encoding="utf-8")
    pdf = root / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n")
    return {"text": text, "json": json_file, "csv": csv_file, "pdf": pdf}


def _sample_value(param: dict[str, Any], item: dict[str, Any], files: dict[str, Path], root: Path) -> Any:
    name = str(param.get("name") or "").lower()
    ann = str(param.get("annotation") or "").lower()
    tool_id = str(item.get("id") or "").lower()

    if name in {"dry_run", "preview", "simulate"}:
        return True
    if "bool" in ann:
        return False
    if "int" in ann and "bool" not in ann:
        if name in {"port"}:
            return 80
        if name in {"x", "y"}:
            return 10
        if name in {"width", "height"}:
            return 120
        if name in {"limit", "number", "num_dice", "sides", "length", "count", "end_page", "start_page", "top_n", "min_size_mb"}:
            return 1
        return 1
    if "float" in ann:
        return 1.0
    if "dict" in ann:
        return {"probe": True}
    if "list" in ann:
        return ["Shell UI probe"]

    if name in {"text", "message", "content", "body", "prompt", "info", "fact", "user_input"}:
        return "Shell UI probe sample"
    if name in {"task", "query", "goal", "complex_task", "mission_objective"}:
        return "UI smoke test only. Return one short safe sentence. Do not modify files or run commands."
    if name in {"subject"}:
        return "Shell UI probe"
    if name in {"recipient", "email", "to"}:
        return "nobody@example.com"
    if name in {"url"}:
        return "https://example.com"
    if name in {"host", "domain"}:
        return "example.com"
    if name in {"platform"}:
        return "telegram"
    if name in {"password"}:
        return "ProbePass123!"
    if name in {"algorithm"}:
        return "sha256"
    if name in {"encoding"}:
        return "base64"
    if name in {"target_lang", "language"}:
        return "Hindi"
    if name in {"from_unit"}:
        return "meter"
    if name in {"to_unit"}:
        return "centimeter"
    if name in {"from_base"}:
        return 10
    if name in {"to_base"}:
        return 2
    if name in {"expression"}:
        return "2 + 3 * 4"
    if name in {"numbers"}:
        return "1, 2, 3, 4"
    if name in {"pattern"}:
        return r"\w+"
    if name in {"replacement"}:
        return "probe"
    if name in {"test_string"}:
        return "Shell UI probe"
    if name in {"json_string", "json_text"}:
        return '{"shell": true}'
    if name in {"case_type"}:
        return "upper"
    if name in {"player_choice"}:
        return "rock"
    if name in {"action"}:
        if "task" in tool_id:
            return "list"
        return "status"
    if name in {"app_title", "app_name", "window_title"}:
        return "Calculator"
    if name in {"filename"}:
        return str(root / "probe_output.txt")
    if name in {"save_path", "output", "output_path"}:
        return str(root / "output.txt")
    if name in {"output_dir", "save_dir", "directory", "directory_path", "folder_path"}:
        return str(root)
    if name in {"filepath", "file_path", "input_path", "source_path"}:
        if "json" in tool_id:
            return str(files["json"])
        if "csv" in tool_id:
            return str(files["csv"])
        if "pdf" in tool_id:
            return str(files["pdf"])
        return str(files["text"])
    if name in {"path"}:
        if "workspace" in tool_id:
            return "ui_probe.txt"
        return str(files["text"])
    if name in {"file1", "file2"}:
        return str(files["json"] if "json" in tool_id else files["pdf"])
    if name in {"input_paths", "pdf_paths", "urls"}:
        return str(files["text"])
    if name in {"zip_path", "tar_path"}:
        return str(root / "archive.zip")
    if name in {"source", "source_text"}:
        return "Shell UI probe"
    if name in {"workflow_name", "task_name", "tag", "project_name", "persona_name", "voice_name"}:
        return "probe"
    if name in {"value"}:
        return 42
    if name in {"cc", "bcc", "attachments", "html_body"}:
        return ""
    return "Shell UI probe"


def _sample_args(item: dict[str, Any], files: dict[str, Path], root: Path) -> dict[str, Any]:
    args: dict[str, Any] = {}
    safe_optional_names = {
        "directory",
        "directory_path",
        "folder_path",
        "filepath",
        "file_path",
        "input_path",
        "source_path",
        "path",
        "output_dir",
        "save_dir",
        "save_path",
        "output_path",
        "dry_run",
        "preview",
        "simulate",
        "top_n",
        "limit",
        "count",
        "min_size_mb",
        "start_page",
        "end_page",
    }
    for param in item.get("params") or []:
        name = str(param.get("name") or "")
        if param.get("required") or name.lower() in safe_optional_names:
            args[name] = _sample_value(param, item, files, root)
    return args


def _should_skip_execution(item: dict[str, Any]) -> tuple[bool, str]:
    tool_id = str(item.get("id") or "")
    category = str(item.get("category") or "")
    blob = " ".join(
        str(item.get(k, ""))
        for k in ("id", "name", "title", "description", "category", "risk")
    )
    meta = item.get("metadata") or {}
    safety = str(meta.get("safety_level") or "")
    if item.get("kind") == "agent":
        return True, "agent readiness-only in full catalog sweep"
    if category in {"ai", "files", "media", "desktop", "system"}:
        return True, f"{category} category readiness-only in full catalog sweep"
    if any(prefix in tool_id.lower() for prefix in ("shell_mcp", "mcp_", "shell_memory")):
        return True, "stateful integration readiness-only in full catalog sweep"
    if safety in {"dangerous", "experimental", "guarded"}:
        return True, f"safety_level={safety}"
    if SAFETY_SKIP_RE.search(blob):
        return True, "mutation/destructive/external-send keyword"
    if ENVIRONMENT_SKIP_RE.search(blob):
        return True, "environment/network-heavy live execution skipped"
    if any(token in tool_id.lower() for token in ("speech", "speak", "voice", "audio", "music", "play_", "vision", "screenshot", "screen", "click", "window")):
        return True, "audio/speech readiness-only in full catalog sweep"
    if tool_id in {
        "shell_window_CTRL:open_app",
        "shell_window_CTRL:close_app",
    }:
        return False, ""
    return False, ""


def _run_item(bridge: Any, item: dict[str, Any], args: dict[str, Any], timeout_s: float) -> dict[str, Any]:
    """Run through the same backend channel used by the Electron Control Center."""
    results: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=1)

    def target() -> None:
        try:
            raw = bridge.call("execute-tool", json.dumps([item.get("id"), args], ensure_ascii=False))
            payload = json.loads(raw) if isinstance(raw, str) else raw
            data = payload.get("data") if isinstance(payload, dict) and "data" in payload else payload
            results.put({"status": "ready", "result": data})
        except Exception as exc:
            results.put({"status": "error", "error": str(exc)})

    thread = threading.Thread(target=target, name="ShellAllToolsProbeItem", daemon=True)
    thread.start()
    thread.join(timeout=max(0.1, float(timeout_s)))
    if thread.is_alive():
        return {"status": "timeout", "error": f"timeout after {timeout_s}s"}
    try:
        return results.get_nowait()
    except queue.Empty:
        return {"status": "error", "error": "tool worker exited without a result"}


def _classify(item: dict[str, Any], outcome: dict[str, Any], skipped: bool, skip_reason: str) -> str:
    if skipped:
        return "skipped_by_safety"
    if outcome.get("status") == "timeout":
        return "timeout"
    if outcome.get("status") == "error":
        message = str(outcome.get("error") or "").lower()
        if any(token in message for token in ("missing api", "api key", "not ready", "missing dependency", "requires windows", "blocked by safety")):
            return "expected_not_ready"
        if "missing required argument" in message:
            return "schema_error"
        return "worker_error"
    result = outcome.get("result")
    if isinstance(result, dict):
        if result.get("status") == "error":
            state = str(result.get("state") or "")
            if state in {"NEEDS_API_KEY", "MISSING_DEPENDENCY", "WINDOWS_ONLY", "BLOCKED_BY_SAFETY", "EXPERIMENTAL"}:
                return "expected_not_ready"
            return "tool_error"
        if result.get("status") == "success":
            return "executed_success"
    return "executed_success"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run every Shell tool through the Electron backend bridge path.")
    parser.add_argument("--visible", action="store_true", help="Accepted for compatibility; the backend bridge probe is headless.")
    parser.add_argument("--json-out", default="/private/tmp/shell_all_tools_ui_probe_report.json")
    parser.add_argument("--screens-dir", default="/private/tmp/shell_all_tools_ui_probe")
    parser.add_argument("--timeout-s", type=float, default=8.0)
    parser.add_argument("--max-execute", type=int, default=0, help="0 = no limit.")
    args = parser.parse_args()

    os.environ.setdefault("SHELL_V2_TIMEOUT_S", "2")
    os.environ.setdefault("SHELL_UI_TOOL_TIMEOUT_S", "2")
    os.environ.setdefault("SHELL_FAST_TOOL_PROBE", "1")

    probe_root = Path(args.screens_dir) / "inputs"
    files = _make_probe_files(probe_root)

    from shell_tool_catalog import discover_tool_catalog
    from core.tools.registry import enrich_catalog
    from shell_web_ui.host import ShellBackendBridge

    rows = enrich_catalog(discover_tool_catalog())
    bridge = ShellBackendBridge()

    report: dict[str, Any] = {
        "ok": True,
        "total": len(rows),
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "results": [],
        "summary": {},
        "runtime": "electron-backend-bridge",
    }
    counts: Counter[str] = Counter()
    executed = 0
    started = time.perf_counter()

    for idx, item in enumerate(rows, 1):
        readiness = item.get("readiness") or {}
        meta = item.get("metadata") or {}
        skip, skip_reason = _should_skip_execution(item)
        readiness_ok = bool(readiness.get("ok"))
        args_for_run = _sample_args(item, files, probe_root) if not skip else {}

        if not skip and not readiness_ok:
            skip = True
            skip_reason = "readiness-only: " + str(readiness.get("state") or "not ready")
        if args.max_execute and executed >= args.max_execute:
            skip = True
            skip_reason = "max execute limit reached"

        row: dict[str, Any] = {
            "index": idx,
            "id": item.get("id"),
            "kind": item.get("kind"),
            "category": item.get("category"),
            "safety_level": meta.get("safety_level"),
            "readiness_state": readiness.get("state"),
            "readiness_ok": readiness.get("ok"),
            "args": args_for_run,
            "skip_reason": skip_reason if skip else "",
        }

        if skip:
            if skip_reason.startswith("readiness-only:"):
                row["classification"] = "expected_not_ready"
                row["status"] = "readiness_only"
                row["message"] = "; ".join(str(reason) for reason in readiness.get("reasons") or [])[:500]
            elif item.get("kind") == "agent":
                row["classification"] = "agent_readiness_only"
                row["status"] = "readiness_only"
                row["message"] = "; ".join(str(reason) for reason in readiness.get("reasons") or [])[:500]
            elif skip_reason.startswith("environment/"):
                row["classification"] = "environment_skipped"
                row["status"] = "skipped"
            else:
                row["classification"] = "skipped_by_safety"
                row["status"] = "skipped"
        else:
            t0 = time.perf_counter()
            outcome = _run_item(bridge, item, args_for_run, timeout_s=args.timeout_s)
            elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            row["elapsed_ms"] = elapsed_ms
            row["status"] = outcome.get("status")
            row["classification"] = _classify(item, outcome, False, "")
            result = outcome.get("result")
            if isinstance(result, dict):
                row["result_status"] = result.get("status")
                row["result_state"] = result.get("state")
                row["message"] = str(result.get("message") or result.get("error") or "")[:500]
                if result.get("reasons"):
                    row["reasons"] = result.get("reasons")
            elif outcome.get("error"):
                row["message"] = str(outcome.get("error"))[:500]
            executed += 1

        counts[row["classification"]] += 1
        report["results"].append(row)

        if idx == 1 or idx % 25 == 0 or idx == len(rows):
            msg = (
                f"All-tools audit progress: {idx}/{len(rows)}. "
                f"Success={counts['executed_success']} "
                f"NotReady={counts['expected_not_ready']} "
                f"SafetySkipped={counts['skipped_by_safety']} "
                f"Errors={counts['tool_error'] + counts['worker_error'] + counts['timeout']}"
            )
            print(msg, flush=True)

    error_count = counts["tool_error"] + counts["worker_error"] + counts["timeout"] + counts["schema_error"]
    report["ok"] = error_count == 0
    report["summary"] = {
        "counts": dict(sorted(counts.items())),
        "executed_workers": executed,
        "duration_s": round(time.perf_counter() - started, 2),
        "readiness_counts": dict(Counter((r.get("readiness") or {}).get("state") for r in rows)),
        "safety_counts": dict(Counter((r.get("metadata") or {}).get("safety_level") for r in rows)),
    }

    out = Path(args.json_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("ok", "total", "summary", "runtime")}, indent=2, sort_keys=True), flush=True)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
