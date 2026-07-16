"""
tools/oauth_manager.py
Manajemen token OAuth — simpan, load, cek expiry, refresh.
Token disimpan di data/oauth_tokens.json.
"""

import json
import logging
import time
from pathlib import Path
from typing import Any

from config.settings import OAUTH_TOKENS_FILE

logger = logging.getLogger(__name__)


def save_tokens(platform: str, token_data: dict[str, Any]) -> None:
    """
    Simpan token OAuth ke file JSON.

    Args:
        platform: 'x' atau 'ig'.
        token_data: Dict berisi access_token, refresh_token, expires_at, dll.
    """
    all_tokens = load_all_tokens()
    token_data["saved_at"] = time.time()
    all_tokens[platform] = token_data

    OAUTH_TOKENS_FILE.parent.mkdir(parents=True, exist_ok=True)
    OAUTH_TOKENS_FILE.write_text(
        json.dumps(all_tokens, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info(f"OAuth token saved for platform: {platform}")


def load_tokens(platform: str) -> dict[str, Any] | None:
    """
    Load token OAuth dari file JSON.

    Args:
        platform: 'x' atau 'ig'.

    Returns:
        Dict token data, atau None jika belum ada.
    """
    all_tokens = load_all_tokens()
    return all_tokens.get(platform)


def load_all_tokens() -> dict[str, Any]:
    """Load semua token dari file."""
    if not OAUTH_TOKENS_FILE.exists():
        return {}
    try:
        return json.loads(OAUTH_TOKENS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, Exception):
        return {}


def is_token_valid(platform: str) -> bool:
    """
    Cek apakah token masih valid (belum expired).

    Args:
        platform: 'x' atau 'ig'.

    Returns:
        True jika token ada dan belum expired.
    """
    token_data = load_tokens(platform)
    if not token_data:
        return False

    access_token = token_data.get("access_token")
    if not access_token:
        return False

    expires_at = token_data.get("expires_at")
    if expires_at and time.time() >= expires_at:
        logger.info(f"Token {platform} sudah expired.")
        return False

    return True


def get_access_token(platform: str) -> str | None:
    """
    Ambil access token untuk platform tertentu.

    Args:
        platform: 'x' atau 'ig'.

    Returns:
        Access token string, atau None jika tidak ada/expired.
    """
    if not is_token_valid(platform):
        return None
    token_data = load_tokens(platform)
    return token_data.get("access_token") if token_data else None


def get_account_info(platform: str) -> dict[str, Any] | None:
    """
    Ambil info akun yang terkoneksi.

    Args:
        platform: 'x' atau 'ig'.

    Returns:
        Dict berisi username, account_id, dll.
    """
    token_data = load_tokens(platform)
    if not token_data:
        return None
    return token_data.get("account_info")


def remove_tokens(platform: str) -> None:
    """Hapus token untuk platform tertentu (logout)."""
    all_tokens = load_all_tokens()
    if platform in all_tokens:
        del all_tokens[platform]
        OAUTH_TOKENS_FILE.write_text(
            json.dumps(all_tokens, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info(f"OAuth token removed for platform: {platform}")


def get_connection_status() -> dict[str, dict]:
    """
    Cek status koneksi semua platform.

    Returns:
        Dict per platform: connected, username, expires_at.
    """
    status = {}
    for platform in ("x", "ig"):
        token_data = load_tokens(platform)
        if token_data and is_token_valid(platform):
            account_info = token_data.get("account_info", {})
            status[platform] = {
                "connected": True,
                "username": account_info.get("username", "Unknown"),
                "display_name": account_info.get("display_name", ""),
                "expires_at": token_data.get("expires_at"),
            }
        else:
            status[platform] = {"connected": False}
    return status
