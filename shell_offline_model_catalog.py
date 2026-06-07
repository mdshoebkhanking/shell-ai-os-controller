"""On-demand offline LLM model catalog for Shell AI.

The Windows installer intentionally does not bundle GGUF chat models. Users can
install one small model from Settings, and the offline LLM runtime discovers it
from the per-user Shell AI model directory.
"""

from __future__ import annotations

import json
import os
import platform
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


CATALOG_VERSION = 1
SELECTED_MODEL_FILE = "selected-model.json"
SELECTED_CODING_MODEL_FILE = "selected-coding-model.json"
MODEL_METADATA_FILE = "shell-model.json"
CHAT_MODEL_CATEGORY = "chat"
CODING_MODEL_CATEGORY = "coding"
MODEL_CATEGORIES = {CHAT_MODEL_CATEGORY, CODING_MODEL_CATEGORY}


@dataclass(frozen=True)
class OfflineModelOption:
    id: str
    name: str
    family: str
    repo: str
    filename: str
    quantization: str
    size_bytes: int
    sha256: str
    license: str
    license_url: str
    min_ram_gb: float
    recommended_ram_gb: float
    pc_tier: str
    description: str
    strengths: tuple[str, ...]
    languages: tuple[str, ...]
    context_tokens: int
    default: bool = False
    category: str = CHAT_MODEL_CATEGORY

    @property
    def download_url(self) -> str:
        return f"https://huggingface.co/{self.repo}/resolve/main/{self.filename}?download=true"

    def as_dict(self, *, install_dir: Path | None = None, system_ram_gb: float | None = None) -> dict[str, Any]:
        target_dir = install_dir or model_install_dir(self.id)
        model_path = target_dir / self.filename
        metadata = read_model_metadata(target_dir)
        installed = model_path.exists() and model_path.is_file()
        if installed and metadata.get("sha256") and str(metadata.get("sha256")).lower() != self.sha256.lower():
            installed = False
        recommended = self.default
        if system_ram_gb is not None:
            recommended = recommended or self.min_ram_gb <= system_ram_gb <= max(self.recommended_ram_gb + 4, self.min_ram_gb)
        payload = asdict(self)
        payload.update(
            {
                "downloadUrl": self.download_url,
                "sizeMb": round(self.size_bytes / 1024 / 1024, 1),
                "installDir": str(target_dir),
                "modelPath": str(model_path),
                "installed": installed,
                "recommended": recommended,
                "catalogVersion": CATALOG_VERSION,
            }
        )
        return payload


OFFLINE_MODEL_OPTIONS: tuple[OfflineModelOption, ...] = (
    OfflineModelOption(
        id="smollm2-135m-q4",
        name="SmolLM2 135M Q4",
        family="SmolLM2-135M-Instruct-GGUF",
        repo="unsloth/SmolLM2-135M-Instruct-GGUF",
        filename="SmolLM2-135M-Instruct-Q4_K_M.gguf",
        quantization="Q4_K_M",
        size_bytes=105_454_144,
        sha256="ed5fa30c487b282ec156c29062f1222e5c20875a944ac98289dbd242e947f747",
        license="Apache-2.0",
        license_url="https://www.apache.org/licenses/LICENSE-2.0",
        min_ram_gb=2.0,
        recommended_ram_gb=3.0,
        pc_tier="Ultra low PC",
        description="Smallest chat brain for very low memory machines.",
        strengths=("basic chat", "short answers", "voice replies"),
        languages=("english",),
        context_tokens=1024,
    ),
    OfflineModelOption(
        id="smollm2-360m-q4",
        name="SmolLM2 360M Q4",
        family="SmolLM2-360M-Instruct-GGUF",
        repo="unsloth/SmolLM2-360M-Instruct-GGUF",
        filename="SmolLM2-360M-Instruct-Q4_K_M.gguf",
        quantization="Q4_K_M",
        size_bytes=270_590_560,
        sha256="16c7f1667fea34bacad196a57b548effcb37614db4ab5677a20c8c7b823b9e63",
        license="Apache-2.0",
        license_url="https://www.apache.org/licenses/LICENSE-2.0",
        min_ram_gb=2.0,
        recommended_ram_gb=4.0,
        pc_tier="Low PC",
        description="Balanced tiny model for 2-4 GB RAM systems.",
        strengths=("chat", "summaries", "voice replies"),
        languages=("english",),
        context_tokens=1536,
    ),
    OfflineModelOption(
        id="qwen2.5-0.5b-q3",
        name="Qwen2.5 0.5B Q3",
        family="Qwen2.5-0.5B-Instruct-GGUF",
        repo="Qwen/Qwen2.5-0.5B-Instruct-GGUF",
        filename="qwen2.5-0.5b-instruct-q3_k_m.gguf",
        quantization="Q3_K_M",
        size_bytes=432_041_824,
        sha256="590d2479d401db206fe12a4562294d2de6211e06338a6e34fbad64b32f1469d0",
        license="Apache-2.0",
        license_url="https://www.apache.org/licenses/LICENSE-2.0",
        min_ram_gb=4.0,
        recommended_ram_gb=6.0,
        pc_tier="4 GB RAM",
        description="Good general offline assistant with a small footprint.",
        strengths=("chat", "Hinglish-style replies", "simple writing"),
        languages=("english", "hindi", "hinglish"),
        context_tokens=1536,
    ),
    OfflineModelOption(
        id="qwen2.5-0.5b-q4",
        name="Qwen2.5 0.5B Q4",
        family="Qwen2.5-0.5B-Instruct-GGUF",
        repo="Qwen/Qwen2.5-0.5B-Instruct-GGUF",
        filename="qwen2.5-0.5b-instruct-q4_k_m.gguf",
        quantization="Q4_K_M",
        size_bytes=491_400_032,
        sha256="74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db",
        license="Apache-2.0",
        license_url="https://www.apache.org/licenses/LICENSE-2.0",
        min_ram_gb=4.0,
        recommended_ram_gb=8.0,
        pc_tier="Recommended",
        description="Recommended local brain for normal chat and voice use.",
        strengths=("chat", "Hinglish-style replies", "reasoning", "short drafting"),
        languages=("english", "hindi", "hinglish"),
        context_tokens=2048,
        default=True,
    ),
    OfflineModelOption(
        id="qwen2.5-coder-0.5b-q4",
        name="Qwen2.5 Coder 0.5B Q4",
        family="Qwen2.5-Coder-0.5B-Instruct-GGUF",
        repo="Qwen/Qwen2.5-Coder-0.5B-Instruct-GGUF",
        filename="qwen2.5-coder-0.5b-instruct-q4_k_m.gguf",
        quantization="Q4_K_M",
        size_bytes=491_400_064,
        sha256="1d9614638d18024d0fbb36575a15f1302a3adf044df10345688ec4f6e1c4ff32",
        license="Apache-2.0",
        license_url="https://www.apache.org/licenses/LICENSE-2.0",
        min_ram_gb=4.0,
        recommended_ram_gb=6.0,
        pc_tier="Coding ultra-light",
        description="Tiny dedicated coding brain for low-memory PCs and short scripts.",
        strengths=("coding", "small scripts", "HTML/CSS drafts", "agent planning"),
        languages=("english", "hindi", "hinglish"),
        context_tokens=1536,
        category=CODING_MODEL_CATEGORY,
    ),
    OfflineModelOption(
        id="qwen2.5-coder-1.5b-q2",
        name="Qwen2.5 Coder 1.5B Q2",
        family="Qwen2.5-Coder-1.5B-Instruct-GGUF",
        repo="Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF",
        filename="qwen2.5-coder-1.5b-instruct-q2_k.gguf",
        quantization="Q2_K",
        size_bytes=752_880_192,
        sha256="3ec56d48cc5acdb93c4323f0d01a3b5db0c73c54fe71831199223720d37f6fcd",
        license="Apache-2.0",
        license_url="https://www.apache.org/licenses/LICENSE-2.0",
        min_ram_gb=6.0,
        recommended_ram_gb=8.0,
        pc_tier="Coding lite",
        description="Smaller coding model for websites, scripts, and structured drafts.",
        strengths=("coding", "website drafts", "PDF/script outlines", "tool planning"),
        languages=("english", "hindi", "hinglish"),
        context_tokens=2048,
        category=CODING_MODEL_CATEGORY,
    ),
    OfflineModelOption(
        id="qwen2.5-coder-1.5b-q4",
        name="Qwen2.5 Coder 1.5B Q4",
        family="Qwen2.5-Coder-1.5B-Instruct-GGUF",
        repo="Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF",
        filename="qwen2.5-coder-1.5b-instruct-q4_k_m.gguf",
        quantization="Q4_K_M",
        size_bytes=1_117_320_768,
        sha256="cc324af070c2ecbfd324a30884d2f951a7ff756aba85cb811a6ec436933bb046",
        license="Apache-2.0",
        license_url="https://www.apache.org/licenses/LICENSE-2.0",
        min_ram_gb=8.0,
        recommended_ram_gb=12.0,
        pc_tier="Best local coding",
        description="Best quality local option in this lightweight catalog.",
        strengths=("coding", "website generation", "longer drafts", "agent planning"),
        languages=("english", "hindi", "hinglish"),
        context_tokens=3072,
        default=True,
        category=CODING_MODEL_CATEGORY,
    ),
)


def _normalized_category(category: str | None) -> str | None:
    if category is None:
        return None
    normalized = str(category or "").strip().lower()
    return normalized if normalized in MODEL_CATEGORIES else CHAT_MODEL_CATEGORY


def model_options(category: str | None = None) -> tuple[OfflineModelOption, ...]:
    normalized = _normalized_category(category)
    if normalized is None:
        return OFFLINE_MODEL_OPTIONS
    return tuple(option for option in OFFLINE_MODEL_OPTIONS if option.category == normalized)


def offline_model_base_dir() -> Path:
    configured = os.environ.get("SHELL_OFFLINE_LLM_MODEL_DIR", "").strip()
    if configured:
        return Path(configured).expanduser()
    system_name = platform.system().lower()
    if system_name.startswith("win"):
        local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
        root = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
        return root / "ShellAI" / "models" / "llm"
    if system_name == "darwin":
        return Path.home() / "Library" / "Application Support" / "ShellAI" / "models" / "llm"
    data_home = os.environ.get("XDG_DATA_HOME", "").strip()
    root = Path(data_home) if data_home else Path.home() / ".local" / "share"
    return root / "ShellAI" / "models" / "llm"


def model_install_dir(model_id: str) -> Path:
    safe_id = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in str(model_id))
    return offline_model_base_dir() / safe_id


def selected_model_path_file(category: str = CHAT_MODEL_CATEGORY) -> Path:
    selected_file = SELECTED_CODING_MODEL_FILE if _normalized_category(category) == CODING_MODEL_CATEGORY else SELECTED_MODEL_FILE
    return offline_model_base_dir() / selected_file


def get_model_option(model_id: str, category: str | None = None) -> OfflineModelOption | None:
    normalized = str(model_id or "").strip()
    for option in model_options(category):
        if option.id == normalized:
            return option
    return None


def option_for_filename(filename: str, category: str | None = None) -> OfflineModelOption | None:
    normalized = str(filename or "").strip().lower()
    for option in model_options(category):
        if option.filename.lower() == normalized:
            return option
    return None


def read_model_metadata(model_dir: Path) -> dict[str, Any]:
    try:
        data = json.loads((model_dir / MODEL_METADATA_FILE).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def write_model_metadata(option: OfflineModelOption, *, model_path: Path, category: str | None = None) -> None:
    selected_category = _normalized_category(category) or option.category
    model_path.parent.mkdir(parents=True, exist_ok=True)
    payload = option.as_dict(install_dir=model_path.parent)
    payload.update(
        {
            "id": option.id,
            "modelPath": str(model_path),
            "sha256": option.sha256,
            "installed": True,
            "category": selected_category,
        }
    )
    (model_path.parent / MODEL_METADATA_FILE).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    selected_path_file = selected_model_path_file(selected_category)
    selected_path_file.parent.mkdir(parents=True, exist_ok=True)
    selected_path_file.write_text(
        json.dumps({"id": option.id, "modelPath": str(model_path)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def installed_model_options(category: str | None = None) -> list[dict[str, Any]]:
    installed: list[dict[str, Any]] = []
    for option in model_options(category):
        payload = option.as_dict()
        if payload.get("installed"):
            installed.append(payload)
    return installed


def selected_installed_model_path(category: str = CHAT_MODEL_CATEGORY) -> Path | None:
    selected_category = _normalized_category(category) or CHAT_MODEL_CATEGORY
    selected_id = ""
    try:
        data = json.loads(selected_model_path_file(selected_category).read_text(encoding="utf-8"))
        if isinstance(data, dict):
            selected_id = str(data.get("id") or "").strip()
    except Exception:
        selected_id = ""
    selected_option = get_model_option(selected_id, selected_category) if selected_id else None
    ordered_options = [selected_option] if selected_option else []
    ordered_options.extend(option for option in model_options(selected_category) if option not in ordered_options)
    for option in ordered_options:
        model_path = model_install_dir(option.id) / option.filename
        if model_path.exists() and model_path.is_file():
            return model_path
    return None


def detect_system_ram_gb() -> float | None:
    try:
        import psutil

        return round(float(psutil.virtual_memory().total) / 1024 / 1024 / 1024, 1)
    except Exception:
        return None


def catalog_payload(category: str = CHAT_MODEL_CATEGORY) -> dict[str, Any]:
    selected_category = _normalized_category(category) or CHAT_MODEL_CATEGORY
    system_ram_gb = detect_system_ram_gb()
    installed = installed_model_options(selected_category)
    selected_path = selected_installed_model_path(selected_category)
    selected_option = option_for_filename(selected_path.name, selected_category) if selected_path else None
    options = [option.as_dict(system_ram_gb=system_ram_gb) for option in model_options(selected_category)]
    return {
        "success": True,
        "catalogVersion": CATALOG_VERSION,
        "category": selected_category,
        "runtimeDownloads": True,
        "installDir": str(offline_model_base_dir()),
        "systemRamGb": system_ram_gb,
        "selectedModelId": selected_option.id if selected_option else "",
        "selectedModelPath": str(selected_path) if selected_path else "",
        "installedModels": installed,
        "options": options,
    }


__all__ = [
    "CHAT_MODEL_CATEGORY",
    "CODING_MODEL_CATEGORY",
    "MODEL_METADATA_FILE",
    "MODEL_CATEGORIES",
    "OFFLINE_MODEL_OPTIONS",
    "OfflineModelOption",
    "catalog_payload",
    "get_model_option",
    "installed_model_options",
    "model_install_dir",
    "model_options",
    "offline_model_base_dir",
    "option_for_filename",
    "selected_installed_model_path",
    "selected_model_path_file",
    "write_model_metadata",
]
