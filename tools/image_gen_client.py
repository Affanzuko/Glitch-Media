"""
tools/image_gen_client.py
Wrapper API image generation — Qwen (DashScope native API).
Retry + exponential backoff.
"""

import logging
import time
import uuid
from pathlib import Path

import requests

from config.settings import (
    IMAGE_GEN_MODEL,
    IMAGE_GEN_API_KEY,
    IMAGES_DIR,
    MAX_RETRIES,
    RETRY_BASE_DELAY,
    RETRY_MAX_DELAY,
    IMAGE_GEN_DASHSCOPE_URL
)

logger = logging.getLogger(__name__)

# ── Endpoint resmi DashScope untuk image generation ──────────────────────────

def generate_image(
    prompt: str,
    run_id: str = "",
    size: str = "1024x1024",
) -> str:
    """
    Generate gambar berdasarkan prompt dan simpan ke data/images/.
    Secara eksklusif menggunakan provider Qwen (DashScope API).
    """
    return _generate_qwen(prompt, run_id, size)


def _generate_qwen(prompt: str, run_id: str, size: str) -> str:
    """Generate gambar via native DashScope API (Qwen)."""
    last_error: Exception | None = None

    # DashScope uses '*' separator (e.g. 1024*1024), not 'x'
    size = size.replace("x", "*")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {IMAGE_GEN_API_KEY}",
        # Header khusus DashScope: enable async task polling
        "X-DashScope-Async": "enable",
    }

    # Payload format DashScope untuk wan2.7-image-pro (messages-based)
    payload = {
        "model": IMAGE_GEN_MODEL,
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"text": prompt}
                    ],
                }
            ]
        },
        "parameters": {
            "size": size,
            "n": 1,
            "negative_prompt": "blurry, low quality, distorted, watermark, text overlay",
            "watermark": False,
        },
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(
                f"Image gen attempt {attempt}/{MAX_RETRIES} "
                f"(provider=qwen, model={IMAGE_GEN_MODEL})"
            )

            # Step 1: Submit task
            response = requests.post(
                IMAGE_GEN_DASHSCOPE_URL,
                headers=headers,
                json=payload,
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()

            # DashScope mengembalikan task_id untuk async polling
            task_id = data.get("output", {}).get("task_id")
            task_status = data.get("output", {}).get("task_status")

            if not task_id:
                raise ValueError(f"DashScope tidak mengembalikan task_id: {data}")

            logger.info(f"Task submitted: {task_id}, status: {task_status}")

            # Step 2: Polling sampai task selesai
            image_url = _poll_task(task_id, headers)

            # Step 3: Download dan simpan gambar
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
                status_code = e.response.status_code if e.response is not None else "unknown"
                resp_text = e.response.text if e.response is not None else str(e)
                logger.warning(f"HTTP error {status_code}, retry in {delay}s: {resp_text}")
                time.sleep(delay)

        except Exception as e:
            last_error = e
            logger.error(f"Unexpected error on attempt {attempt}: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BASE_DELAY)

    raise RuntimeError(
        f"Image gen gagal setelah {MAX_RETRIES} attempts. Last error: {last_error}"
    )


def _poll_task(task_id: str, headers: dict, max_wait: int = 120) -> str:
    """Polling status task DashScope sampai selesai dan return URL gambar."""
    # Derive base URL from the configured endpoint
    # IMAGE_GEN_DASHSCOPE_URL = .../api/v1/services/aigc/image-generation/generation
    # We need:                    .../api/v1/tasks/{task_id}
    base_url = IMAGE_GEN_DASHSCOPE_URL.split("/services/")[0]
    task_url = f"{base_url}/tasks/{task_id}"
    elapsed = 0
    interval = 3  # cek setiap 3 detik

    while elapsed < max_wait:
        time.sleep(interval)
        elapsed += interval

        resp = requests.get(task_url, headers={"Authorization": headers["Authorization"]}, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        status = data.get("output", {}).get("task_status", "")
        logger.info(f"Task {task_id}: status={status} ({elapsed}s elapsed)")

        if status == "SUCCEEDED":
            # Format baru (wan2.7): output.choices[].message.content[].image
            choices = data.get("output", {}).get("choices", [])
            if choices:
                content_list = choices[0].get("message", {}).get("content", [])
                for item in content_list:
                    if item.get("type") == "image" and item.get("image"):
                        return item["image"]
                    # Fallback: cek key 'image' tanpa 'type'
                    if item.get("image") and not item.get("type"):
                        return item["image"]

            # Format lama (wanx-v1): output.results[].url
            results = data.get("output", {}).get("results", [])
            if results and results[0].get("url"):
                return results[0]["url"]
            # Fallback: cek di b64_image
            if results and results[0].get("b64_image"):
                import base64
                image_bytes = base64.b64decode(results[0]["b64_image"])
                image_path = _save_image_bytes(image_bytes, "")
                return image_path

            raise ValueError(f"Task SUCCEEDED tapi tidak ada URL gambar: {data}")

        elif status == "FAILED":
            error_msg = data.get("output", {}).get("message", "Unknown error")
            raise RuntimeError(f"Task gagal: {error_msg}")

        elif status in ("PENDING", "RUNNING"):
            continue
        else:
            logger.warning(f"Status tidak dikenal: {status}")

    raise TimeoutError(f"Task {task_id} timeout setelah {max_wait}s")


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
