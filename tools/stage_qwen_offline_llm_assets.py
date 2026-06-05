from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.request
from pathlib import Path
from typing import NamedTuple


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "models" / "llm" / "qwen3"


class LLMAsset(NamedTuple):
    name: str
    url: str
    min_bytes: int


MODEL_VARIANTS = {
    "q8_official": LLMAsset(
        "Qwen3-1.7B-Q8_0.gguf",
        "https://huggingface.co/Qwen/Qwen3-1.7B-GGUF/resolve/main/Qwen3-1.7B-Q8_0.gguf?download=true",
        1_700_000_000,
    ),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def valid_existing(path: Path, min_bytes: int) -> bool:
    return path.exists() and path.stat().st_size >= min_bytes


def download_asset(asset: LLMAsset, output_dir: Path, *, dry_run: bool, force: bool) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / asset.name
    if valid_existing(target, asset.min_bytes) and not force:
        return {
            "name": asset.name,
            "status": "cached",
            "path": str(target),
            "size_bytes": target.stat().st_size,
            "sha256": sha256(target),
            "url": asset.url,
        }
    if dry_run:
        return {
            "name": asset.name,
            "status": "dry-run",
            "path": str(target),
            "size_bytes": 0,
            "sha256": "",
            "url": asset.url,
        }

    tmp_target = target.with_suffix(target.suffix + ".download")
    if tmp_target.exists():
        tmp_target.unlink()
    with urllib.request.urlopen(asset.url, timeout=300) as response:
        with tmp_target.open("wb") as handle:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
    if tmp_target.stat().st_size < asset.min_bytes:
        tmp_target.unlink(missing_ok=True)
        raise RuntimeError(f"Downloaded {asset.name} is too small; expected at least {asset.min_bytes} bytes.")
    tmp_target.replace(target)
    return {
        "name": asset.name,
        "status": "downloaded",
        "path": str(target),
        "size_bytes": target.stat().st_size,
        "sha256": sha256(target),
        "url": asset.url,
    }


def stage_assets(*, output_dir: Path, variant: str, dry_run: bool, force: bool) -> dict[str, object]:
    if variant not in MODEL_VARIANTS:
        raise RuntimeError(f"Unsupported Qwen offline LLM variant: {variant}")
    asset = MODEL_VARIANTS[variant]
    staged = [download_asset(asset, output_dir, dry_run=dry_run, force=force)]
    report = {
        "status": "dry-run" if dry_run else "ready",
        "model_family": "Qwen3-1.7B-GGUF",
        "model_repo": "Qwen/Qwen3-1.7B-GGUF",
        "runtime": "llama-cpp-python",
        "variant": variant,
        "output_dir": str(output_dir),
        "created_at": time.time(),
        "runtime_downloads": False,
        "assets": staged,
    }
    if not dry_run:
        (output_dir / "qwen-offline-llm-assets.json").write_text(
            json.dumps(report, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stage Qwen3 offline LLM GGUF assets for installer builds.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--variant", choices=sorted(MODEL_VARIANTS), default="q8_official")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = stage_assets(output_dir=args.output_dir, variant=args.variant, dry_run=args.dry_run, force=args.force)
    except Exception as exc:
        print(f"Qwen offline LLM asset staging failed: {exc}")
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
