#!/usr/bin/env python3
"""
Shell Crypto Tools — Encryption, Hashing & Password Generation
"""
import os
import hashlib
import secrets
import string
import base64
import logging
from shell_safe_executor import god_tier_tool as function_tool

logger = logging.getLogger("shell_crypto")


# ── Encryption helpers ──────────────────────────────────────────

# PBKDF2 with per-message salt. Iteration count follows OWASP 2023
# guidance for SHA-256 (≥600k); we use 600_000 which takes ~200 ms on
# a modern CPU — acceptable for a CLI tool, painful for an attacker.
_PBKDF2_ITERATIONS = 600_000
_PBKDF2_SALT_LEN = 16
_KEY_LEN = 32


def _derive_key(password: str, salt: bytes) -> bytes:
    """Derive a 32-byte key via PBKDF2-HMAC-SHA256 with per-message salt.

    The old code used single-pass SHA-256 of the raw password — trivially
    brute-forceable. PBKDF2 forces ≥600k hash rounds per guess.
    """
    if not isinstance(salt, (bytes, bytearray)) or len(salt) < _PBKDF2_SALT_LEN:
        raise ValueError(f"salt must be ≥{_PBKDF2_SALT_LEN} bytes")
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes(salt), _PBKDF2_ITERATIONS, dklen=_KEY_LEN,
    )


def _xor_bytes(data: bytes, key: bytes) -> bytes:
    """XOR data with a repeating key. Kept only for legacy-token decryption."""
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


def _encrypt_data(data: bytes, password: str) -> str:
    """Encrypt bytes using Fernet (preferred) or AES-free XOR (fallback).

    Both paths now include a random salt so the same plaintext encrypted
    twice produces different ciphertext. Salt is stored in the token so
    decryption works without needing to remember it separately.

    Token formats:
      * FERNET:<base64salt>.<fernet-token>   — preferred (AES-128-CBC + HMAC)
      * XOR   :<base64salt>.<base64xor>       — fallback, not cryptographically secure
    """
    salt = secrets.token_bytes(_PBKDF2_SALT_LEN)
    try:
        from cryptography.fernet import Fernet
        key = base64.urlsafe_b64encode(_derive_key(password, salt))
        f = Fernet(key)
        fernet_token = f.encrypt(data).decode("utf-8")
        return "FERNET:" + base64.b64encode(salt).decode("ascii") + "." + fernet_token
    except ImportError:
        key = _derive_key(password, salt)
        encrypted = _xor_bytes(data, key)
        return (
            "XOR:" + base64.b64encode(salt).decode("ascii")
            + "." + base64.b64encode(encrypted).decode("utf-8")
        )


def _decrypt_data(token: str, password: str) -> bytes:
    """Decrypt data encrypted by `_encrypt_data`.

    Accepts both the new salted format and the pre-Phase-20 unsalted
    format so old encrypted values still decrypt. New encryptions
    always use the salted path.
    """
    if token.startswith("FERNET:"):
        body = token[len("FERNET:"):]
        if "." in body:
            salt_b64, fernet_token = body.split(".", 1)
            salt = base64.b64decode(salt_b64)
        else:
            # Legacy unsalted token — derive from empty salt (matches old SHA-256).
            fernet_token = body
            salt = b"\x00" * _PBKDF2_SALT_LEN
        from cryptography.fernet import Fernet
        # Legacy tokens used raw SHA-256; detect by salt being all-zero.
        if salt == b"\x00" * _PBKDF2_SALT_LEN:
            key_bytes = hashlib.sha256(password.encode("utf-8")).digest()
        else:
            key_bytes = _derive_key(password, salt)
        key = base64.urlsafe_b64encode(key_bytes)
        f = Fernet(key)
        return f.decrypt(fernet_token.encode("utf-8"))
    elif token.startswith("XOR:"):
        body = token[len("XOR:"):]
        if "." in body:
            salt_b64, xor_b64 = body.split(".", 1)
            salt = base64.b64decode(salt_b64)
            key = _derive_key(password, salt)
        else:
            xor_b64 = body
            key = hashlib.sha256(password.encode("utf-8")).digest()  # legacy
        encrypted = base64.b64decode(xor_b64)
        return _xor_bytes(encrypted, key)
    else:
        raise ValueError("Unknown encryption format. Token must start with 'FERNET:' or 'XOR:'.")


# ═══════════════════════════════════════════════════════════════
#  TOOL 1: ENCRYPT TEXT
# ═══════════════════════════════════════════════════════════════

@function_tool
async def encrypt_text_tool(text: str, password: str) -> str:
    """
    Encrypt text using a password.
    Uses Fernet (cryptography library) if available, otherwise base64+XOR fallback.
    Args:
        text: The plaintext to encrypt.
        password: The password used for encryption.
    """
    try:
        encrypted = _encrypt_data(text.encode("utf-8"), password)
        method = "Fernet (AES-128-CBC)" if encrypted.startswith("FERNET:") else "XOR+Base64 (fallback)"
        return (
            f"Text encrypted successfully.\n"
            f"Method: {method}\n"
            f"Encrypted ({len(encrypted)} chars):\n{encrypted}"
        )
    except Exception as e:
        return f"Encryption failed: {e}"


# ═══════════════════════════════════════════════════════════════
#  TOOL 2: DECRYPT TEXT
# ═══════════════════════════════════════════════════════════════

@function_tool
async def decrypt_text_tool(encrypted: str, password: str) -> str:
    """
    Decrypt text that was encrypted with encrypt_text_tool.
    Args:
        encrypted: The encrypted token string (starts with FERNET: or XOR:).
        password: The password used during encryption.
    """
    try:
        decrypted = _decrypt_data(encrypted.strip(), password)
        return f"Decrypted text:\n{decrypted.decode('utf-8')}"
    except Exception as e:
        return f"Decryption failed: {e}"


# ═══════════════════════════════════════════════════════════════
#  TOOL 3: HASH TEXT
# ═══════════════════════════════════════════════════════════════

@function_tool
async def hash_text_tool(text: str, algorithm: str = "sha256") -> str:
    """
    Hash text using the specified algorithm.
    Args:
        text: The text to hash.
        algorithm: Hash algorithm — md5, sha1, sha256, sha512. Default: sha256.
    """
    algo = algorithm.lower().strip()
    supported = {"md5", "sha1", "sha256", "sha512"}
    if algo not in supported:
        return f"Unsupported algorithm '{algo}'. Supported: {', '.join(sorted(supported))}"
    try:
        h = hashlib.new(algo, text.encode("utf-8"))
        digest = h.hexdigest()
        return (
            f"Algorithm: {algo.upper()}\n"
            f"Input length: {len(text)} chars\n"
            f"Hash: {digest}"
        )
    except Exception as e:
        return f"Hashing failed: {e}"


# ═══════════════════════════════════════════════════════════════
#  TOOL 4: HASH FILE
# ═══════════════════════════════════════════════════════════════

@function_tool
async def hash_file_tool(filepath: str, algorithm: str = "sha256") -> str:
    """
    Compute the hash of a file.
    Args:
        filepath: Path to the file to hash.
        algorithm: Hash algorithm — md5, sha1, sha256, sha512. Default: sha256.
    """
    algo = algorithm.lower().strip()
    supported = {"md5", "sha1", "sha256", "sha512"}
    if algo not in supported:
        return f"Unsupported algorithm '{algo}'. Supported: {', '.join(sorted(supported))}"
    if not os.path.isfile(filepath):
        return f"File not found: {filepath}"
    try:
        h = hashlib.new(algo)
        size = os.path.getsize(filepath)
        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                h.update(chunk)
        digest = h.hexdigest()
        size_str = f"{size / 1024:.1f} KB" if size >= 1024 else f"{size} B"
        return (
            f"File: {os.path.basename(filepath)}\n"
            f"Size: {size_str}\n"
            f"Algorithm: {algo.upper()}\n"
            f"Hash: {digest}"
        )
    except Exception as e:
        return f"File hashing failed: {e}"


# ═══════════════════════════════════════════════════════════════
#  TOOL 5: GENERATE PASSWORD
# ═══════════════════════════════════════════════════════════════

@function_tool
async def generate_password_tool(length: int = 16) -> str:
    """
    Generate a cryptographically secure random password.
    Args:
        length: Password length (8-128). Default: 16.
    """
    length = max(8, min(128, length))
    try:
        alphabet = string.ascii_letters + string.digits + string.punctuation
        # Ensure at least one of each category
        password_chars = [
            secrets.choice(string.ascii_lowercase),
            secrets.choice(string.ascii_uppercase),
            secrets.choice(string.digits),
            secrets.choice(string.punctuation),
        ]
        password_chars += [secrets.choice(alphabet) for _ in range(length - 4)]
        # Shuffle using secrets for uniform randomness
        result = list(password_chars)
        for i in range(len(result) - 1, 0, -1):
            j = secrets.randbelow(i + 1)
            result[i], result[j] = result[j], result[i]
        password = "".join(result)
        return (
            f"Generated password ({length} chars):\n{password}\n\n"
            f"Contains: uppercase, lowercase, digits, symbols\n"
            f"Entropy: ~{length * 6.5:.0f} bits"
        )
    except Exception as e:
        return f"Password generation failed: {e}"


# ═══════════════════════════════════════════════════════════════
#  TOOL 6: ENCRYPT FILE
# ═══════════════════════════════════════════════════════════════

@function_tool
async def encrypt_file_tool(filepath: str, password: str) -> str:
    """
    Encrypt a file and save as .encrypted.
    Args:
        filepath: Path to the file to encrypt.
        password: Password for encryption.
    """
    if not os.path.isfile(filepath):
        return f"File not found: {filepath}"
    try:
        with open(filepath, "rb") as f:
            data = f.read()
        size_before = len(data)
        encrypted = _encrypt_data(data, password)
        output_path = filepath + ".encrypted"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(encrypted)
        size_after = os.path.getsize(output_path)
        method = "Fernet" if encrypted.startswith("FERNET:") else "XOR+Base64"
        return (
            f"File encrypted successfully.\n"
            f"Method: {method}\n"
            f"Original: {os.path.basename(filepath)} ({size_before} bytes)\n"
            f"Encrypted: {os.path.basename(output_path)} ({size_after} bytes)\n"
            f"Saved to: {output_path}"
        )
    except Exception as e:
        return f"File encryption failed: {e}"
