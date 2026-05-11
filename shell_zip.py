#!/usr/bin/env python3
"""
Shell ZIP/Archive Tools — Create, Extract, List, and Manage Archives
"""
import os
import zipfile
import tarfile
import logging
from shell_safe_executor import god_tier_tool as function_tool

logger = logging.getLogger("shell_zip")


def _human_size(size_bytes: int) -> str:
    """Convert bytes to human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


# ═══════════════════════════════════════════════════════════════
#  TOOL 1: CREATE ZIP ARCHIVE
# ═══════════════════════════════════════════════════════════════

@function_tool
async def zip_create_tool(source_path: str, zip_path: str) -> str:
    """
    Create a ZIP archive from a file or folder.
    Args:
        source_path: Path to file or directory to compress.
        zip_path: Output ZIP file path (e.g., 'archive.zip').
    """
    if not os.path.exists(source_path):
        return f"Source not found: {source_path}"
    try:
        if not zip_path.lower().endswith(".zip"):
            zip_path += ".zip"
        file_count = 0
        total_size = 0
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            if os.path.isfile(source_path):
                zf.write(source_path, os.path.basename(source_path))
                file_count = 1
                total_size = os.path.getsize(source_path)
            else:
                for root, dirs, files in os.walk(source_path):
                    for file in files:
                        full_path = os.path.join(root, file)
                        arcname = os.path.relpath(full_path, os.path.dirname(source_path))
                        zf.write(full_path, arcname)
                        file_count += 1
                        total_size += os.path.getsize(full_path)
        zip_size = os.path.getsize(zip_path)
        ratio = (1 - zip_size / total_size) * 100 if total_size > 0 else 0
        return (
            f"ZIP created successfully.\n"
            f"Source: {source_path}\n"
            f"Archive: {zip_path}\n"
            f"Files: {file_count}\n"
            f"Original size: {_human_size(total_size)}\n"
            f"Compressed size: {_human_size(zip_size)}\n"
            f"Compression ratio: {ratio:.1f}%"
        )
    except Exception as e:
        return f"ZIP creation failed: {e}"


# ═══════════════════════════════════════════════════════════════
#  TOOL 2: EXTRACT ZIP ARCHIVE
# ═══════════════════════════════════════════════════════════════

@function_tool
async def zip_extract_tool(zip_path: str, output_dir: str) -> str:
    """
    Extract a ZIP archive to a directory.
    Args:
        zip_path: Path to the ZIP file.
        output_dir: Directory to extract files into.
    """
    if not os.path.isfile(zip_path):
        return f"ZIP file not found: {zip_path}"
    try:
        os.makedirs(output_dir, exist_ok=True)
        output_real = os.path.realpath(output_dir) + os.sep
        with zipfile.ZipFile(zip_path, "r") as zf:
            # Fix zip-slip TOCTOU: validate AND extract each member inside the
            # same loop. The old code validated all members, then called
            # extractall() afterwards — between the two, a symlink could be
            # swapped to point outside output_dir.
            names = zf.namelist()
            for member in names:
                # Reject absolute paths and parent-directory references up front.
                if member.startswith("/") or member.startswith("\\") or ".." in member.replace("\\", "/").split("/"):
                    return f"Security error: ZIP contains unsafe entry '{member}'."
                member_target = os.path.realpath(os.path.join(output_dir, member))
                if not (member_target + os.sep).startswith(output_real) and member_target + os.sep != output_real:
                    return f"Security error: ZIP entry '{member}' resolves outside output_dir."
                # Extract this single member only; re-check that extractall
                # never sees the whole archive as one shot.
                zf.extract(member, path=output_dir)
        return (
            f"ZIP extracted successfully.\n"
            f"Archive: {zip_path}\n"
            f"Destination: {output_dir}\n"
            f"Files extracted: {len(names)}\n"
            f"Contents:\n" + "\n".join(f"  - {n}" for n in names[:30])
            + (f"\n  ... and {len(names) - 30} more" if len(names) > 30 else "")
        )
    except zipfile.BadZipFile:
        return f"Error: '{zip_path}' is not a valid ZIP file."
    except Exception as e:
        return f"ZIP extraction failed: {e}"


# ═══════════════════════════════════════════════════════════════
#  TOOL 3: LIST ZIP CONTENTS
# ═══════════════════════════════════════════════════════════════

@function_tool
async def zip_list_tool(zip_path: str) -> str:
    """
    List the contents of a ZIP archive with file sizes.
    Args:
        zip_path: Path to the ZIP file.
    """
    if not os.path.isfile(zip_path):
        return f"ZIP file not found: {zip_path}"
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            infos = zf.infolist()
        if not infos:
            return f"ZIP archive '{zip_path}' is empty."
        lines = [f"Contents of: {os.path.basename(zip_path)}"]
        lines.append(f"{'Name':<50} {'Size':>12} {'Compressed':>12}")
        lines.append("-" * 76)
        total_size = 0
        total_compressed = 0
        for info in infos:
            total_size += info.file_size
            total_compressed += info.compress_size
            lines.append(
                f"{info.filename:<50} {_human_size(info.file_size):>12} {_human_size(info.compress_size):>12}"
            )
        lines.append("-" * 76)
        lines.append(f"Total: {len(infos)} files, {_human_size(total_size)} -> {_human_size(total_compressed)}")
        return "\n".join(lines)
    except zipfile.BadZipFile:
        return f"Error: '{zip_path}' is not a valid ZIP file."
    except Exception as e:
        return f"Failed to list ZIP contents: {e}"


# ═══════════════════════════════════════════════════════════════
#  TOOL 4: ADD FILE TO ZIP
# ═══════════════════════════════════════════════════════════════

@function_tool
async def zip_add_tool(zip_path: str, file_path: str) -> str:
    """
    Add a file to an existing ZIP archive.
    Args:
        zip_path: Path to the existing ZIP file.
        file_path: Path to the file to add.
    """
    if not os.path.isfile(zip_path):
        return f"ZIP file not found: {zip_path}"
    if not os.path.isfile(file_path):
        return f"File not found: {file_path}"
    try:
        with zipfile.ZipFile(zip_path, "a", zipfile.ZIP_DEFLATED) as zf:
            arcname = os.path.basename(file_path)
            zf.write(file_path, arcname)
        file_size = os.path.getsize(file_path)
        zip_size = os.path.getsize(zip_path)
        return (
            f"File added to ZIP successfully.\n"
            f"Added: {arcname} ({_human_size(file_size)})\n"
            f"Archive: {zip_path} ({_human_size(zip_size)})"
        )
    except Exception as e:
        return f"Failed to add file to ZIP: {e}"


# ═══════════════════════════════════════════════════════════════
#  TOOL 5: CREATE TAR.GZ ARCHIVE
# ═══════════════════════════════════════════════════════════════

@function_tool
async def tar_create_tool(source_path: str, tar_path: str) -> str:
    """
    Create a tar.gz (gzipped tar) archive from a file or folder.
    Args:
        source_path: Path to file or directory to compress.
        tar_path: Output tar.gz file path (e.g., 'archive.tar.gz').
    """
    if not os.path.exists(source_path):
        return f"Source not found: {source_path}"
    try:
        if not tar_path.lower().endswith((".tar.gz", ".tgz")):
            tar_path += ".tar.gz"
        file_count = 0
        with tarfile.open(tar_path, "w:gz") as tf:
            if os.path.isfile(source_path):
                tf.add(source_path, arcname=os.path.basename(source_path))
                file_count = 1
            else:
                for root, dirs, files in os.walk(source_path):
                    for file in files:
                        full_path = os.path.join(root, file)
                        arcname = os.path.relpath(full_path, os.path.dirname(source_path))
                        tf.add(full_path, arcname=arcname)
                        file_count += 1
        tar_size = os.path.getsize(tar_path)
        return (
            f"TAR.GZ created successfully.\n"
            f"Source: {source_path}\n"
            f"Archive: {tar_path}\n"
            f"Files: {file_count}\n"
            f"Archive size: {_human_size(tar_size)}"
        )
    except Exception as e:
        return f"TAR.GZ creation failed: {e}"
