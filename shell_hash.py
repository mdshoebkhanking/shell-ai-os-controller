#!/usr/bin/env python3
"""
Shell Hash Tools — Hashing, checksum, and file integrity utilities.
All tools use Python stdlib: hashlib, os, pathlib.
"""

import os
import hashlib
import logging
from pathlib import Path
from shell_safe_executor import god_tier_tool as function_tool

logger = logging.getLogger("shell_hash")

# Supported hash algorithms
_ALGORITHMS = {
    "md5": hashlib.md5,
    "sha1": hashlib.sha1,
    "sha256": hashlib.sha256,
    "sha512": hashlib.sha512,
    "sha3_256": hashlib.sha3_256,
    "sha3_512": hashlib.sha3_512,
}

_CHUNK_SIZE = 8192


def _hash_file(filepath: str, algo_name: str) -> str:
    """Hash a file using the specified algorithm."""
    algo_func = _ALGORITHMS.get(algo_name)
    if not algo_func:
        raise ValueError(f"Unknown algorithm: {algo_name}")
    h = algo_func()
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(_CHUNK_SIZE)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _file_size_str(size: int) -> str:
    """Human-readable file size."""
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    elif size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.2f} MB"
    else:
        return f"{size / (1024 * 1024 * 1024):.2f} GB"


# ═══════════════════════════════════════════════════════════════
#  TOOL 1: HASH STRING
# ═══════════════════════════════════════════════════════════════

@function_tool
async def hash_string_tool(text: str, algorithm: str) -> str:
    """
    Hash a string using the specified algorithm.
    Args:
        text: The string to hash.
        algorithm: Hash algorithm — one of: md5, sha1, sha256, sha512, sha3_256, sha3_512.
    """
    try:
        algo = algorithm.lower().strip()
        if algo not in _ALGORITHMS:
            supported = ", ".join(_ALGORITHMS.keys())
            return f"Unknown algorithm: '{algorithm}'. Supported: {supported}"

        h = _ALGORITHMS[algo]()
        h.update(text.encode("utf-8"))
        digest = h.hexdigest()

        return (
            f"Hash Result:\n"
            f"  Algorithm: {algo}\n"
            f"  Input:     {len(text)} chars\n"
            f"  Digest:    {digest}\n"
            f"  Length:    {len(digest)} hex chars ({len(digest) * 4} bits)"
        )
    except Exception as e:
        return f"Error hashing string: {e}"


# ═══════════════════════════════════════════════════════════════
#  TOOL 2: HASH FILE
# ═══════════════════════════════════════════════════════════════

@function_tool
async def hash_file_tool(filepath: str) -> str:
    """
    Calculate MD5 and SHA-256 hashes for a file.
    Args:
        filepath: Path to the file to hash.
    """
    try:
        if not os.path.exists(filepath):
            return f"Error: File not found: {filepath}"
        if not os.path.isfile(filepath):
            return f"Error: Not a file: {filepath}"

        file_size = os.path.getsize(filepath)
        # SHA-256 is the default integrity hash. MD5 is still computed
        # for cross-checking against external tools that report it, but
        # it's clearly labeled as "legacy" so users don't trust it for
        # tamper-detection (MD5 collisions are feasible).
        sha256_hash = _hash_file(filepath, "sha256")
        sha512_hash = _hash_file(filepath, "sha512")
        md5_hash = _hash_file(filepath, "md5")

        fname = os.path.basename(filepath)
        return (
            f"File Hashes for: {fname}\n"
            f"  Path:        {filepath}\n"
            f"  Size:        {_file_size_str(file_size)}\n"
            f"  SHA256:      {sha256_hash}\n"
            f"  SHA512:      {sha512_hash}\n"
            f"  MD5 (legacy, collision-prone — do not trust for integrity): {md5_hash}"
        )
    except PermissionError:
        return f"Error: Permission denied: {filepath}"
    except Exception as e:
        return f"Error hashing file: {e}"


# ═══════════════════════════════════════════════════════════════
#  TOOL 3: VERIFY HASH
# ═══════════════════════════════════════════════════════════════

@function_tool
async def verify_hash_tool(filepath: str, expected_hash: str) -> str:
    """
    Verify file integrity by comparing against an expected hash.
    Automatically detects the algorithm based on hash length.
    Args:
        filepath: Path to the file to verify.
        expected_hash: The expected hash value to compare against.
    """
    try:
        if not os.path.exists(filepath):
            return f"Error: File not found: {filepath}"

        expected = expected_hash.strip().lower()
        hash_len = len(expected)

        # Auto-detect algorithm from hash length
        algo_by_length = {
            32: "md5",
            40: "sha1",
            64: "sha256",
            128: "sha512",
        }

        algo = algo_by_length.get(hash_len)
        if not algo:
            return (
                f"Error: Cannot detect algorithm from hash length ({hash_len} chars).\n"
                f"Expected lengths: MD5=32, SHA1=40, SHA256=64, SHA512=128"
            )

        actual_hash = _hash_file(filepath, algo)
        match = actual_hash == expected

        fname = os.path.basename(filepath)
        status = "MATCH — File integrity verified!" if match else "MISMATCH — File may be corrupted or modified!"
        symbol = "+" if match else "!"

        return (
            f"[{symbol}] Verification: {status}\n"
            f"  File:      {fname}\n"
            f"  Algorithm: {algo.upper()}\n"
            f"  Expected:  {expected}\n"
            f"  Actual:    {actual_hash}"
        )
    except Exception as e:
        return f"Error verifying hash: {e}"


# ═══════════════════════════════════════════════════════════════
#  TOOL 4: CHECKSUM DIRECTORY
# ═══════════════════════════════════════════════════════════════

@function_tool
async def checksum_dir_tool(directory: str) -> str:
    """
    Generate SHA-256 checksums for all files in a directory (recursive).
    Args:
        directory: Path to the directory to checksum.
    """
    try:
        if not os.path.exists(directory):
            return f"Error: Directory not found: {directory}"
        if not os.path.isdir(directory):
            return f"Error: Not a directory: {directory}"

        results = []
        total_size = 0
        errors = 0
        skipped = 0

        for root, dirs, files in os.walk(directory):
            # Skip hidden dirs and common large directories
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", "__pycache__", ".git", "venv")]

            for fname in sorted(files):
                fpath = os.path.join(root, fname)
                try:
                    fsize = os.path.getsize(fpath)
                    if fsize > 100 * 1024 * 1024:  # Skip files > 100MB
                        skipped += 1
                        continue
                    total_size += fsize
                    sha = _hash_file(fpath, "sha256")
                    rel_path = os.path.relpath(fpath, directory)
                    results.append(f"{sha}  {rel_path}")
                except (PermissionError, OSError):
                    errors += 1
                    continue

        if not results:
            return f"No files found in: {directory}"

        header = (
            f"Checksums for: {directory}\n"
            f"Files: {len(results)} | Total size: {_file_size_str(total_size)}"
        )
        if errors:
            header += f" | Errors: {errors}"
        if skipped:
            header += f" | Skipped (>100MB): {skipped}"
        header += f"\n{'=' * 55}"

        # Limit output to first 200 files
        if len(results) > 200:
            body = "\n".join(results[:200])
            body += f"\n... and {len(results) - 200} more files"
        else:
            body = "\n".join(results)

        return f"{header}\n{body}"
    except Exception as e:
        return f"Error generating checksums: {e}"
