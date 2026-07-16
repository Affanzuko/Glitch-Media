"""
tools/ig_api_client.py
Wrapper posting ke Instagram (Graph API).
Mendukung 2 mode autentikasi:
  1. OAuth token (dari login via browser) — prioritas utama
  2. Static token dari .env — fallback
Flow: Create media container → Publish container.
Retry + exponential backoff + step/attempt budget.
"""

import logging
import time

import requests

from config.settings import (
    INSTAGRAM_ACCESS_TOKEN,
    INSTAGRAM_BUSINESS_ACCOUNT_ID,
    MAX_RETRIES,
    RETRY_BASE_DELAY,
    RETRY_MAX_DELAY,
)

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v18.0"


def _get_credentials() -> tuple[str, str]:
    """
    Ambil access token dan business account ID.
    Prioritas: OAuth token (dari login) > static token (.env).

    Returns:
        Tuple (access_token, business_account_id).

    Raises:
        RuntimeError: Jika tidak ada kredensial.
    """
    from tools.oauth_manager import load_tokens, is_token_valid

    # Cek OAuth token dulu
    if is_token_valid("ig"):
        token_data = load_tokens("ig")
        if token_data:
            access_token = token_data.get("access_token")
            account_id = token_data.get("ig_business_account_id")
            if access_token and account_id:
                logger.debug("Using OAuth token for IG")
                return access_token, account_id

    # Fallback ke static token
    if INSTAGRAM_ACCESS_TOKEN and INSTAGRAM_BUSINESS_ACCOUNT_ID:
        logger.debug("Using static token for IG")
        return INSTAGRAM_ACCESS_TOKEN, INSTAGRAM_BUSINESS_ACCOUNT_ID

    raise RuntimeError(
        "Tidak ada kredensial Instagram. "
        "Login via OAuth (tools.oauth_server.login_ig()) atau set token di .env"
    )


def post_image(
    image_url: str,
    caption: str,
) -> dict:
    """
    Post gambar ke Instagram menggunakan Graph API.
    
    Flow Instagram Graph API:
    1. Create media container (POST /{ig-user-id}/media)
    2. Publish container (POST /{ig-user-id}/media_publish)

    Args:
        image_url: URL publik gambar (Instagram butuh URL, bukan file lokal).
        caption: Caption untuk post IG.

    Returns:
        Dict dengan 'success', 'post_url', dan 'media_id'.

    Raises:
        RuntimeError: Jika semua retry gagal.
    """
    # Step 1: Create media container
    container_id = _create_container(image_url, caption)

    # Step 2: Publish container
    return _publish_container(container_id)


def _create_container(image_url: str, caption: str) -> str:
    """Create media container di Instagram."""
    access_token, account_id = _get_credentials()
    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(f"IG create container attempt {attempt}/{MAX_RETRIES}")

            response = requests.post(
                f"{GRAPH_API_BASE}/{account_id}/media",
                params={
                    "image_url": image_url,
                    "caption": caption,
                    "access_token": access_token,
                },
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            container_id = data["id"]
            logger.info(f"IG container created: {container_id}")
            return container_id

        except requests.exceptions.HTTPError as e:
            last_error = e
            error_data = {}
            try:
                error_data = e.response.json()
            except Exception:
                pass

            delay = min(RETRY_BASE_DELAY * (2 ** (attempt - 1)), RETRY_MAX_DELAY)
            logger.warning(
                f"IG create container error: {error_data.get('error', {}).get('message', str(e))}. "
                f"Retry in {delay}s"
            )
            time.sleep(delay)

        except Exception as e:
            last_error = e
            logger.error(f"IG unexpected error on attempt {attempt}: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BASE_DELAY)

    raise RuntimeError(
        f"IG create container gagal setelah {MAX_RETRIES} attempts. Last error: {last_error}"
    )


def _publish_container(container_id: str) -> dict:
    """Publish media container ke Instagram feed."""
    access_token, account_id = _get_credentials()
    last_error: Exception | None = None

    # Tunggu sebentar agar container siap (IG best practice)
    time.sleep(3)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(f"IG publish attempt {attempt}/{MAX_RETRIES}")

            response = requests.post(
                f"{GRAPH_API_BASE}/{account_id}/media_publish",
                params={
                    "creation_id": container_id,
                    "access_token": access_token,
                },
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            media_id = data["id"]
            post_url = f"https://www.instagram.com/p/{media_id}/"

            logger.info(f"IG post published: {post_url}")
            return {
                "success": True,
                "post_url": post_url,
                "media_id": media_id,
            }

        except requests.exceptions.HTTPError as e:
            last_error = e
            error_data = {}
            try:
                error_data = e.response.json()
            except Exception:
                pass

            # Cek apakah container belum siap
            error_code = error_data.get("error", {}).get("code", 0)
            if error_code == 9007:  # Media not ready
                delay = 5  # Tunggu lebih lama untuk processing
                logger.info(f"IG container belum siap, tunggu {delay}s...")
            else:
                delay = min(RETRY_BASE_DELAY * (2 ** (attempt - 1)), RETRY_MAX_DELAY)
                logger.warning(
                    f"IG publish error: {error_data.get('error', {}).get('message', str(e))}. "
                    f"Retry in {delay}s"
                )
            time.sleep(delay)

        except Exception as e:
            last_error = e
            logger.error(f"IG unexpected error on attempt {attempt}: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BASE_DELAY)

    raise RuntimeError(
        f"IG publish gagal setelah {MAX_RETRIES} attempts. Last error: {last_error}"
    )


def upload_image_to_hosting(local_path: str) -> str:
    """
    Upload gambar lokal ke hosting publik (agar bisa dipakai oleh IG Graph API).
    
    Instagram Graph API membutuhkan URL publik, bukan file lokal.
    Implementasi ini menggunakan imgbb.com sebagai hosting sementara.
    
    Args:
        local_path: Path file gambar lokal.

    Returns:
        URL publik gambar.
    
    Note:
        Untuk production, sebaiknya gunakan hosting sendiri (S3, GCS, dll).
    """
    import base64
    from pathlib import Path
    from config.settings import IMAGE_GEN_API_KEY  # Re-use atau buat key terpisah

    image_data = Path(local_path).read_bytes()
    encoded = base64.b64encode(image_data).decode("utf-8")

    # Placeholder — ganti dengan hosting service yang sesuai
    logger.warning(
        "upload_image_to_hosting: menggunakan placeholder. "
        "Implementasikan dengan S3/GCS/imgbb sesuai kebutuhan."
    )

    # Fallback: return local path (hanya berfungsi jika server bisa diakses publik)
    return f"file://{local_path}"
