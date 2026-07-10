"""
tools/image_gen_client.py
Wrapper API image generation — mendukung OpenAI DALL-E (default).
Retry + exponential backoff.
"""

import logging
import time
import uuid
from pathlib import Path

import requests

from config.settings import (
    IMAGE_GEN_API_KEY,
    IMAGE_GEN_PROVIDER,
    IMAGE_GEN_MODEL,
    IMAGES_DIR,
    MAX_RETRIES,
    RETRY_BASE_DELAY,
    RETRY_MAX_DELAY,
)

logger = logging.getLogger(__name__)


def generate_image(
    prompt: str,
    run_id: str = "",
    size: str = "1024x1024",
) -> str:
    """
    Generate gambar berdasarkan prompt dan simpan ke data/images/.

    Args:
        prompt: Text prompt untuk image generation.
        run_id: ID run pipeline (untuk penamaan file).
        size: Ukuran gambar (default 1024x1024 untuk IG square).

    Returns:
        Path lokal file gambar yang disimpan.

    Raises:
        RuntimeError: Jika semua retry gagal.
    """
    if IMAGE_GEN_PROVIDER == "openai":
        return _generate_openai(prompt, run_id, size)
    elif IMAGE_GEN_PROVIDER == "stability":
        return _generate_stability(prompt, run_id, size)
    else:
        raise ValueError(f"Unsupported image gen provider: {IMAGE_GEN_PROVIDER}")


def _generate_openai(prompt: str, run_id: str, size: str) -> str:
    """Generate gambar via OpenAI DALL-E API."""
    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(
                f"Image gen attempt {attempt}/{MAX_RETRIES} "
                f"(provider=openai, model={IMAGE_GEN_MODEL})"
            )

            response = requests.post(
                "https://api.openai.com/v1/images/generations",
                headers={
                    "Authorization": f"Bearer {IMAGE_GEN_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": IMAGE_GEN_MODEL,
                    "prompt": prompt,
                    "n": 1,
                    "size": size,
                    "response_format": "url",
                },
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()

            image_url = data["data"][0]["url"]

            # Download dan simpan gambar
            image_path = _download_and_save(image_url, run_id)
            logger.info(f"Image gen sukses: {image_path}")
            return image_path

        except requests.exceptions.HTTPError as e:
            last_error = e
            if e.response is not None and e.response.status_code == 429:
                delay = min(RETRY_BASE_DELAY * (2 ** (attempt - 1)), RETRY_MAX_DELAY)
                logger.warning(f"Rate limited, retry in {delay}s")
                time.sleep(delay)
            else:
                delay = min(RETRY_BASE_DELAY * (2 ** (attempt - 1)), RETRY_MAX_DELAY)
                logger.warning(f"HTTP error {e.response.status_code}, retry in {delay}s: {e}")
                time.sleep(delay)

        except Exception as e:
            last_error = e
            logger.error(f"Unexpected error on attempt {attempt}: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BASE_DELAY)

    raise RuntimeError(
        f"Image gen gagal setelah {MAX_RETRIES} attempts. Last error: {last_error}"
    )


def _generate_stability(prompt: str, run_id: str, size: str) -> str:
    """Generate gambar via Stability AI API."""
    last_error: Exception | None = None

    # Parse size
    width, height = (int(x) for x in size.split("x"))

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(
                f"Image gen attempt {attempt}/{MAX_RETRIES} (provider=stability)"
            )

            response = requests.post(
                "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image",
                headers={
                    "Authorization": f"Bearer {IMAGE_GEN_API_KEY}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json={
                    "text_prompts": [{"text": prompt, "weight": 1.0}],
                    "cfg_scale": 7,
                    "width": width,
                    "height": height,
                    "samples": 1,
                    "steps": 30,
                },
                timeout=120,
            )
            response.raise_for_status()
            data = response.json()

            # Stability returns base64 encoded images
            import base64

            image_data = base64.b64decode(data["artifacts"][0]["base64"])
            image_path = _save_image_bytes(image_data, run_id)
            logger.info(f"Image gen sukses: {image_path}")
            return image_path

        except Exception as e:
            last_error = e
            delay = min(RETRY_BASE_DELAY * (2 ** (attempt - 1)), RETRY_MAX_DELAY)
            logger.warning(f"Stability error on attempt {attempt}, retry in {delay}s: {e}")
            time.sleep(delay)

    raise RuntimeError(
        f"Image gen (stability) gagal setelah {MAX_RETRIES} attempts. Last error: {last_error}"
    )


def _download_and_save(image_url: str, run_id: str) -> str:
    """Download gambar dari URL dan simpan ke data/images/."""
    response = requests.get(image_url, timeout=30)
    response.raise_for_status()
    return _save_image_bytes(response.content, run_id)


def _save_image_bytes(image_bytes: bytes, run_id: str) -> str:
    """Simpan bytes gambar ke file lokal."""
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    filename = f"{run_id}_{uuid.uuid4().hex[:8]}.png" if run_id else f"{uuid.uuid4().hex}.png"
    file_path = IMAGES_DIR / filename

    file_path.write_bytes(image_bytes)
    return str(file_path)
