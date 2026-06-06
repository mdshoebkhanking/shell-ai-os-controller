from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import NamedTuple


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = ROOT / "models" / "stt" / "sherpa-onnx"
MODEL_DIR_NAME = "sherpa-onnx-streaming-zipformer-en-20M-2023-02-17"
MODEL_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
    "sherpa-onnx-streaming-zipformer-en-20M-2023-02-17.tar.bz2"
)
MODEL_FAMILY = "sherpa-onnx streaming Zipformer EN 20M"
MODEL_KIND = "transducer"
MODEL_SOURCE = "k2-fsa/sherpa-onnx asr-models"


class STTAsset(NamedTuple):
    name: str
    min_bytes: int


REQUIRED_ASSETS = (
    STTAsset("tokens.txt", 1_000),
    STTAsset("encoder-epoch-99-avg-1.int8.onnx", 35_000_000),
    STTAsset("decoder-epoch-99-avg-1.onnx", 1_500_000),
    STTAsset("joiner-epoch-99-avg-1.int8.onnx", 100_000),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def model_dir(output_root: Path) -> Path:
    return output_root / MODEL_DIR_NAME


def valid_existing(path: Path, min_bytes: int) -> bool:
    return path.exists() and path.stat().st_size >= min_bytes


def required_assets_ready(target_dir: Path) -> bool:
    return all(valid_existing(target_dir / asset.name, asset.min_bytes) for asset in REQUIRED_ASSETS)


def _download_archive(target: Path) -> None:
    tmp_target = target.with_suffix(target.suffix + ".download")
    if tmp_target.exists():
        tmp_target.unlink()
    with urllib.request.urlopen(MODEL_URL, timeout=180) as response:
        with tmp_target.open("wb") as handle:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
    if tmp_target.stat().st_size < 100_000_000:
        tmp_target.unlink(missing_ok=True)
        raise RuntimeError("Downloaded sherpa-onnx STT archive is too small.")
    tmp_target.replace(target)


def _extract_archive(archive: Path, output_root: Path) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:bz2") as tar:
        root = output_root.resolve()
        for member in tar.getmembers():
            destination = (output_root / member.name).resolve()
            if root not in destination.parents and destination != root:
                raise RuntimeError(f"Refusing unsafe archive path: {member.name}")
        tar.extractall(output_root)


def _write_metadata(target_dir: Path, assets: list[dict[str, object]], *, status: str) -> None:
    report = {
        "status": status,
        "model_family": MODEL_FAMILY,
        "model_kind": MODEL_KIND,
        "runtime": "sherpa-onnx",
        "language_support": ["english", "hinglish"],
        "sample_rate": 16000,
        "feature_dim": 80,
        "output_dir": str(target_dir),
        "created_at": time.time(),
        "source_release": MODEL_SOURCE,
        "source_url": MODEL_URL,
        "runtime_downloads": False,
        "assets": assets,
        "preferred_files": {
            "tokens": "tokens.txt",
            "encoder": "encoder-epoch-99-avg-1.int8.onnx",
            "decoder": "decoder-epoch-99-avg-1.onnx",
            "joiner": "joiner-epoch-99-avg-1.int8.onnx",
        },
    }
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "shell-stt-assets.json").write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def stage_assets(*, output_root: Path, dry_run: bool, force: bool) -> dict[str, object]:
    target_dir = model_dir(output_root)
    if required_assets_ready(target_dir) and not force:
        assets = [
            {
                "name": asset.name,
                "status": "cached",
                "path": str(target_dir / asset.name),
                "size_bytes": (target_dir / asset.name).stat().st_size,
                "sha256": sha256(target_dir / asset.name),
                "url": MODEL_URL,
            }
            for asset in REQUIRED_ASSETS
        ]
        _write_metadata(target_dir, assets, status="ready")
        return {
            "status": "ready",
            "model_family": MODEL_FAMILY,
            "runtime": "sherpa-onnx",
            "output_dir": str(target_dir),
            "assets": assets,
            "source_url": MODEL_URL,
        }

    if dry_run:
        return {
            "status": "dry-run",
            "model_family": MODEL_FAMILY,
            "runtime": "sherpa-onnx",
            "output_dir": str(target_dir),
            "assets": [
                {
                    "name": asset.name,
                    "status": "dry-run",
                    "path": str(target_dir / asset.name),
                    "size_bytes": 0,
                    "sha256": "",
                    "url": MODEL_URL,
                }
                for asset in REQUIRED_ASSETS
            ],
            "source_url": MODEL_URL,
        }

    with tempfile.TemporaryDirectory(prefix="shell-stt-assets-") as temp_dir:
        archive = Path(temp_dir) / f"{MODEL_DIR_NAME}.tar.bz2"
        _download_archive(archive)
        _extract_archive(archive, output_root)

    missing = [
        asset.name
        for asset in REQUIRED_ASSETS
        if not valid_existing(target_dir / asset.name, asset.min_bytes)
    ]
    if missing:
        raise RuntimeError("Sherpa STT staging did not produce required assets: " + ", ".join(missing))

    assets = [
        {
            "name": asset.name,
            "status": "downloaded",
            "path": str(target_dir / asset.name),
            "size_bytes": (target_dir / asset.name).stat().st_size,
            "sha256": sha256(target_dir / asset.name),
            "url": MODEL_URL,
        }
        for asset in REQUIRED_ASSETS
    ]
    _write_metadata(target_dir, assets, status="ready")
    return {
        "status": "ready",
        "model_family": MODEL_FAMILY,
        "runtime": "sherpa-onnx",
        "output_dir": str(target_dir),
        "assets": assets,
        "source_url": MODEL_URL,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stage sherpa-onnx offline STT assets for installer builds.")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = stage_assets(output_root=args.output_root, dry_run=args.dry_run, force=args.force)
    except Exception as exc:
        print(f"Sherpa STT asset staging failed: {exc}")
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
