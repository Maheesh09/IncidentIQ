# utils/auth.py
from __future__ import annotations

import hashlib
import secrets
import string


# API key format: iqk_live_<40 random chars>
API_KEY_PREFIX = "iqk_live_"
API_KEY_LENGTH = 40


def generate_api_key() -> tuple[str, str, str]:
    """Generate a new API key with its hash and prefix.

    The raw key is shown to the customer once and never stored.
    Only the hash is stored in the database.

    Returns:
        Tuple of (raw_key, key_hash, key_prefix).
        raw_key: The full key shown to the customer once.
        key_hash: SHA-256 hash stored in the database.
        key_prefix: First 12 chars for display in dashboard.
    """
    alphabet = string.ascii_letters + string.digits
    random_part = "".join(
        secrets.choice(alphabet) for _ in range(API_KEY_LENGTH)
    )
    raw_key = f"{API_KEY_PREFIX}{random_part}"
    key_hash = hash_api_key(raw_key)
    key_prefix = raw_key[:12]
    return raw_key, key_hash, key_prefix


def hash_api_key(raw_key: str) -> str:
    """Compute SHA-256 hash of a raw API key.

    Args:
        raw_key: The full API key string.

    Returns:
        Hex-encoded SHA-256 hash string.
    """
    return hashlib.sha256(raw_key.encode()).hexdigest()