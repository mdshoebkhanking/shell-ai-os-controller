#!/usr/bin/env python3
"""Shell AI UI/UX design-system audit.

This is a deterministic audit for the parts of UI quality that can be
checked without a human screenshot review: theme contrast, design docs,
source ownership, beginner-flow hooks, and media structure.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / ".shell_runtime" / "ui_ux_audit_report.json"


@dataclass(frozen=True)
class AuditFinding:
    severity: str
    category: str
    message: str
    path: str = ""
    value: object | None = None


def _source_files() -> Iterable[Path]:
    excluded = {"__pycache__", "build", "dist"}
    for path in (ROOT / "shell_ui").rglob("*.py"):
        if excluded.intersection(path.parts):
            continue
        yield path


def _line_count(path: Path) -> int:
    try:
        return len(path.read_text(encoding="utf-8", errors="ignore").splitlines())
    except OSError:
        return 0


def _style_hotspots(path: Path) -> int:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return 0
    return len(re.findall(r"\bsetStyleSheet\s*\(", text))


def _docs_present(findings: list[AuditFinding]) -> dict[str, bool]:
    required = {
        "DESIGN.md": ROOT / "DESIGN.md",
        "UI/UX report": ROOT / "docs" / "UI_UX_PHASE6_REPORT.md",
        "Product experience plan": ROOT / "docs" / "PRODUCT_EXPERIENCE_DESIGN.md",
        "Screenshot demo strategy": ROOT / "docs" / "SCREENSHOT_DEMO_STRATEGY.md",
    }
    present = {name: path.exists() for name, path in required.items()}
    for name, ok in present.items():
        if not ok:
            findings.append(
                AuditFinding(
                    severity="medium",
                    category="documentation",
                    message=f"Missing design documentation: {name}",
                    path=str(required[name].relative_to(ROOT)),
                )
            )
    return present


def _media_structure(findings: list[AuditFinding]) -> dict[str, bool]:
    folders = ["screenshots", "gifs", "videos", "banners"]
    present = {name: (ROOT / name).is_dir() for name in folders}
    for name, ok in present.items():
        if not ok:
            findings.append(
                AuditFinding(
                    severity="medium",
                    category="media",
                    message=f"Missing public showcase folder: {name}/",
                    path=name,
                )
            )
    return present


def _theme_audit(findings: list[AuditFinding]) -> dict[str, object]:
    sys.path.insert(0, str(ROOT))
    from shell_ui import design_tokens as tokens

    contrast_issues = tokens.audit_palette_contrast()
    for issue in contrast_issues:
        findings.append(
            AuditFinding(
                severity=issue.severity,
                category="accessibility",
                message=(
                    f"{issue.theme} {issue.token} contrast {issue.ratio}:1 "
                    f"is below {issue.required}:1"
                ),
                value=asdict(issue),
            )
        )

    missing_meta = [
        name for name in tokens.PALETTES
        if name not in getattr(tokens, "THEME_METADATA", {})
    ]
    for name in missing_meta:
        findings.append(
            AuditFinding(
                severity="medium",
                category="theme",
                message=f"Theme metadata missing for {name}",
            )
        )
    return {
        "theme_count": len(tokens.PALETTES),
        "theme_names": list(tokens.PALETTES.keys()),
        "contrast_issues": [asdict(issue) for issue in contrast_issues],
        "metadata_complete": not missing_meta,
    }


def _source_audit(findings: list[AuditFinding]) -> dict[str, object]:
    files = list(_source_files())
    line_counts = {str(p.relative_to(ROOT)): _line_count(p) for p in files}
    style_counts = {str(p.relative_to(ROOT)): _style_hotspots(p) for p in files}

    monolith = ROOT / "shell_ui" / "shell_cinematic_full.py"
    monolith_lines = _line_count(monolith)
    if monolith_lines > 10000:
        findings.append(
            AuditFinding(
                severity="medium",
                category="maintainability",
                message="Main PyQt host is still monolithic; continue staged extraction.",
                path=str(monolith.relative_to(ROOT)),
                value=monolith_lines,
            )
        )

    biggest_style_files = sorted(
        style_counts.items(), key=lambda item: item[1], reverse=True
    )[:5]
    if biggest_style_files and biggest_style_files[0][1] > 80:
        findings.append(
            AuditFinding(
                severity="low",
                category="visual_consistency",
                message="Inline QSS remains concentrated in a few files.",
                value=biggest_style_files,
            )
        )

    return {
        "source_files": len(files),
        "total_ui_lines": sum(line_counts.values()),
        "main_host_lines": monolith_lines,
        "largest_files": sorted(
            line_counts.items(), key=lambda item: item[1], reverse=True
        )[:8],
        "style_hotspots": biggest_style_files,
    }


def _score(findings: list[AuditFinding]) -> int:
    penalties = {"high": 18, "medium": 7, "low": 3, "info": 1}
    score = 100
    for finding in findings:
        score -= penalties.get(finding.severity, 3)
    return max(0, score)


def build_report() -> dict[str, object]:
    findings: list[AuditFinding] = []
    theme = _theme_audit(findings)
    source = _source_audit(findings)
    docs = _docs_present(findings)
    media = _media_structure(findings)
    score = _score(findings)
    return {
        "name": "Shell AI UI/UX Phase 6 Audit",
        "score": score,
        "status": "pass" if not any(f.severity == "high" for f in findings) else "attention",
        "theme": theme,
        "source": source,
        "docs": docs,
        "media": media,
        "findings": [asdict(f) for f in findings],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Shell AI UI/UX audit")
    parser.add_argument("--json", action="store_true", help="Print full JSON report")
    parser.add_argument("--fail-on-high", action="store_true", help="Exit non-zero on high findings")
    args = parser.parse_args(argv)

    report = build_report()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Shell AI UI/UX audit: {report['score']}/100 ({report['status'].upper()})")
        print(f"Report: {REPORT_PATH.relative_to(ROOT)}")
        counts: dict[str, int] = {}
        for finding in report["findings"]:
            counts[finding["severity"]] = counts.get(finding["severity"], 0) + 1
        print(f"Findings: {counts or {'none': 0}}")

    if args.fail_on_high and report["status"] != "pass":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
