"""
tools/llm_client.py
Unified LLM client — mendukung dua provider:
  - LOCAL  : 9Router (proxy lokal, OpenAI-compatible)  → development
  - CLOUD  : Alibaba Cloud DashScope compatible-mode   → production

Fitur:
  - Auto-detect provider dari LLM_PROVIDER env
  - Retry dengan exponential backoff
  - Fallback ke model alternatif jika model utama gagal
  - Handling SSE stream fallback
  - JSON extraction dari response LLM
"""

import json
import logging
import re
import time

import requests

from config.settings import (
    LLM_PROVIDER,
    NINEROUTER_BASE_URL,
    DASHSCOPE_API_KEY,
    DASHSCOPE_BASE_URL,
    LLM_MAX_TOKENS,
    LLM_TEMPERATURE,
    MAX_RETRIES,
    RETRY_BASE_DELAY,
    RETRY_MAX_DELAY,
    get_fallback_chain,
)

logger = logging.getLogger(__name__)

# ── HTTP error codes yang layak di-retry / pindah model ──────────────────────
_RETRYABLE_STATUS_CODES = {
    429,  # Rate limit / quota exceeded / token habis
    500,  # Internal server error
    502,  # Bad gateway
    503,  # Service unavailable
    504,  # Gateway timeout
}

# HTTP status yang menandakan harus pindah model (bukan retry model yang sama)
_MODEL_SWITCH_STATUS_CODES = {
    429,  # Rate limit / quota / token habis → pindah model lain
    403,  # Forbidden — model mungkin tidak tersedia / quota habis
}


def _get_provider_config(model: str) -> tuple[str, dict[str, str]]:
    """
    Return (endpoint_url, headers) berdasarkan LLM_PROVIDER aktif.

    Raises:
        ValueError: jika konfigurasi provider tidak lengkap.
    """
    if LLM_PROVIDER == "cloud":
        # ── Alibaba Cloud DashScope (compatible-mode / OpenAI-compatible) ────
        if not DASHSCOPE_API_KEY:
            raise ValueError(
                "LLM_PROVIDER='cloud' tapi DASHSCOPE_API_KEY kosong. "
                "Set DASHSCOPE_API_KEY di .env."
            )
        url = f"{DASHSCOPE_BASE_URL.rstrip('/')}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
        }
        return url, headers

    else:
        # ── 9Router (local proxy) ───────────────────────────────────────────
        if not NINEROUTER_BASE_URL:
            raise ValueError(
                "LLM_PROVIDER='local' tapi NINEROUTER_BASE_URL kosong. "
                "Set NINEROUTER_BASE_URL di .env atau jalankan 9Router."
            )
        url = f"{NINEROUTER_BASE_URL.rstrip('/')}/chat/completions"
        headers = {"Content-Type": "application/json"}
        return url, headers


def _build_payload(model: str, system_prompt: str, user_message: str) -> dict:
    """Bangun request payload OpenAI-compatible."""
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "response_format": {"type": "json_object"},
        "temperature": LLM_TEMPERATURE,
        "max_tokens": LLM_MAX_TOKENS,
        "stream": False,
    }


def _extract_content(response: requests.Response) -> str:
    """
    Ekstrak content text dari response LLM.
    Handle dua kasus:
      1. SSE stream (data: ...) — jika router memaksa stream meski stream=False
      2. JSON standard — format normal OpenAI-compatible
    """
    raw_text = response.text.strip()

    if raw_text.startswith("data:"):
        # ── Parsing Server-Sent Events (SSE) ─────────────────────────────
        content_parts: list[str] = []
        for line in raw_text.splitlines():
            line = line.strip()
            if line.startswith("data: ") and line != "data: [DONE]":
                try:
                    chunk = json.loads(line[6:])
                    choices = chunk.get("choices", [])
                    if choices:
                        delta = choices[0].get("delta", {})
                        if "content" in delta:
                            content_parts.append(delta["content"])
                except json.JSONDecodeError:
                    continue
        content = "".join(content_parts)
    else:
        # ── Parsing JSON standard ────────────────────────────────────────
        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            raise ValueError(f"Response tidak punya 'choices': {data}")
        content = choices[0].get("message", {}).get("content", "")

    if not content:
        raise ValueError("Response LLM kosong (content empty).")

    return content


def _extract_json(content: str) -> str:
    """
    Ekstrak JSON object dari content LLM.
    Coba:
      1. Blok markdown ```json ... ``` atau ``` ... ```
      2. Kurung kurawal terluar { ... }
      3. Content apa adanya (mungkin sudah JSON murni)
    """
    # 1. Cari di dalam blok markdown
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL)
    if match:
        return match.group(1).strip()

    # 2. Cari kurung kurawal terluar
    start = content.find("{")
    end = content.rfind("}")
    if start != -1 and end != -1 and end > start:
        return content[start : end + 1].strip()

    # 3. Fallback: return apa adanya
    return content.strip()


def _is_model_switch_error(exc: Exception) -> bool:
    """
    Cek apakah error menandakan harus pindah ke model lain
    (token habis, rate limit, quota exceeded, model unavailable).
    """
    if isinstance(exc, requests.exceptions.HTTPError):
        if exc.response is not None:
            status = exc.response.status_code
            if status in _MODEL_SWITCH_STATUS_CODES:
                return True
            # Cek body response untuk indikasi token/quota habis
            try:
                body = exc.response.text.lower()
                quota_keywords = [
                    "quota", "token", "limit", "exceeded",
                    "insufficient", "exhausted", "billing",
                    "rate_limit", "rate limit",
                ]
                if any(kw in body for kw in quota_keywords):
                    return True
            except Exception:
                pass
    if isinstance(exc, RuntimeError):
        msg = str(exc).lower()
        if any(kw in msg for kw in ["429", "quota", "token", "limit", "exceeded"]):
            return True
    return False


def _is_retryable_error(exc: Exception) -> bool:
    """Cek apakah error layak di-retry (pada model yang sama)."""
    if isinstance(exc, requests.exceptions.HTTPError):
        if exc.response is not None:
            return exc.response.status_code in _RETRYABLE_STATUS_CODES
    if isinstance(exc, (requests.exceptions.ConnectionError,
                        requests.exceptions.Timeout)):
        return True
    return False


def _calculate_delay(attempt: int) -> float:
    """Hitung delay exponential backoff dengan cap."""
    delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
    return min(delay, RETRY_MAX_DELAY)


def call_llm(
    system_prompt: str,
    user_message: str,
    response_schema: type,
    model: str,
    agent_name: str = "caption_x",
) -> object:
    """
    Panggil LLM dan return data sesuai response_schema (Pydantic model).

    Flow (per-agent fallback chain):
      1. Coba model utama dengan retry + exponential backoff
      2. Jika gagal karena token habis / rate limit / quota exceeded:
         → pindah ke model berikutnya di fallback chain agent tersebut
      3. Ulangi sampai semua model di chain habis dicoba
      4. Jika semua gagal → raise RuntimeError dengan log lengkap

    Contoh chain CLOUD untuk caption agents:
      Qwen3.7-Plus → Qwen3.7-Max → GLM-5.2

    Args:
        system_prompt: System prompt untuk LLM.
        user_message: User message / data input.
        response_schema: Pydantic model class untuk validasi output.
        model: Model ID utama (sudah di-resolve oleh settings.get_model_for_agent).
        agent_name: Nama agent pemanggil (untuk resolve fallback chain).

    Returns:
        Instance dari response_schema yang sudah tervalidasi.

    Raises:
        RuntimeError: Jika semua model di chain gagal.
        ValueError: Jika response LLM tidak bisa di-parse/validasi.
    """
    provider_label = "DashScope" if LLM_PROVIDER == "cloud" else "9Router"

    # Bangun urutan model: [model utama] + [fallback chain agent tanpa duplikat]
    fallback_chain = get_fallback_chain(agent_name)
    model_chain: list[str] = [model]
    for fb_model in fallback_chain:
        if fb_model not in model_chain:
            model_chain.append(fb_model)

    logger.info(
        f"LLM call: provider={provider_label}, "
        f"model_chain={' → '.join(model_chain)}"
    )

    # Track semua error per model untuk laporan akhir
    errors: dict[str, str] = {}

    for idx, current_model in enumerate(model_chain):
        is_primary = (idx == 0)
        label = "primary" if is_primary else f"fallback-{idx}"

        logger.info(
            f"[{label}] Mencoba model '{current_model}' "
            f"({idx + 1}/{len(model_chain)})"
        )

        try:
            result = _call_with_retry(
                model=current_model,
                system_prompt=system_prompt,
                user_message=user_message,
                response_schema=response_schema,
            )
            if not is_primary:
                logger.info(
                    f"[{label}] Model '{current_model}' berhasil "
                    f"(setelah model sebelumnya gagal)"
                )
            return result

        except ValueError:
            # Pydantic validation error — data dari LLM tidak valid.
            # Tidak perlu pindah model, karena masalahnya di output format.
            # Langsung raise agar caller tahu.
            raise

        except Exception as e:
            error_msg = str(e)
            errors[current_model] = error_msg

            # Cek apakah error ini menandakan harus pindah model
            should_switch = _is_model_switch_error(e)

            if should_switch and idx < len(model_chain) - 1:
                next_model = model_chain[idx + 1]
                logger.warning(
                    f"[{label}] Model '{current_model}' gagal "
                    f"(token/quota/rate limit). "
                    f"Pindah ke '{next_model}'... "
                    f"Error: {error_msg[:200]}"
                )
                continue  # Lanjut ke model berikutnya

            elif idx < len(model_chain) - 1:
                # Error bukan karena quota, tapi masih ada model lain → coba juga
                next_model = model_chain[idx + 1]
                logger.warning(
                    f"[{label}] Model '{current_model}' gagal "
                    f"(non-quota error). "
                    f"Tetap mencoba '{next_model}'... "
                    f"Error: {error_msg[:200]}"
                )
                continue

            else:
                # Model terakhir di chain, tidak ada lagi yang bisa dicoba
                logger.error(
                    f"[{label}] Model '{current_model}' gagal. "
                    f"Tidak ada model lain di chain."
                )

    # Semua model di chain gagal — buat laporan lengkap
    error_report = "\n".join(
        f"  [{i+1}] {m}: {err[:150]}"
        for i, (m, err) in enumerate(errors.items())
    )
    raise RuntimeError(
        f"Semua model di fallback chain gagal.\n"
        f"Provider: {provider_label}\n"
        f"Chain: {' → '.join(model_chain)}\n"
        f"Errors:\n{error_report}"
    )


def _call_with_retry(
    model: str,
    system_prompt: str,
    user_message: str,
    response_schema: type,
) -> object:
    """
    Kirim request ke LLM dengan retry + exponential backoff.

    Retry dilakukan untuk:
      - HTTP 429 (rate limit)
      - HTTP 500/502/503/504 (server error)
      - ConnectionError / Timeout

    Non-retryable errors (400, 401, 403, dll) langsung raise.
    """
    url, headers = _get_provider_config(model)
    payload = _build_payload(model, system_prompt, user_message)

    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.debug(
                f"LLM request attempt {attempt}/{MAX_RETRIES} "
                f"→ model={model}, provider={LLM_PROVIDER}"
            )

            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=120,  # 2 menit timeout per request
            )
            response.raise_for_status()

            # Ekstrak content dari response
            content = _extract_content(response)

            # Ekstrak JSON dari content
            json_str = _extract_json(content)

            # Validasi via Pydantic
            try:
                return response_schema.model_validate_json(json_str)
            except Exception as validation_err:
                raise ValueError(
                    f"Gagal validasi Pydantic.\n"
                    f"Model: {model}\n"
                    f"LLM Output: {json_str[:500]}"
                ) from validation_err

        except requests.exceptions.HTTPError as e:
            last_error = e
            status_code = e.response.status_code if e.response is not None else "?"
            resp_body = e.response.text[:300] if e.response is not None else str(e)

            if _is_retryable_error(e) and attempt < MAX_RETRIES:
                delay = _calculate_delay(attempt)
                logger.warning(
                    f"HTTP {status_code} pada attempt {attempt}/{MAX_RETRIES}. "
                    f"Retry dalam {delay:.1f}s. Body: {resp_body}"
                )
                time.sleep(delay)
            else:
                # Non-retryable atau attempt terakhir
                logger.error(
                    f"HTTP {status_code} — tidak bisa retry. Body: {resp_body}"
                )
                raise RuntimeError(
                    f"LLM API error (HTTP {status_code}).\n"
                    f"Model: {model}\n"
                    f"Provider: {LLM_PROVIDER}\n"
                    f"Response: {resp_body}"
                ) from e

        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout) as e:
            last_error = e
            if attempt < MAX_RETRIES:
                delay = _calculate_delay(attempt)
                logger.warning(
                    f"Koneksi error pada attempt {attempt}/{MAX_RETRIES}: {e}. "
                    f"Retry dalam {delay:.1f}s."
                )
                time.sleep(delay)
            else:
                raise RuntimeError(
                    f"Koneksi ke LLM gagal setelah {MAX_RETRIES} attempt.\n"
                    f"Model: {model}\n"
                    f"Provider: {LLM_PROVIDER}\n"
                    f"Error: {e}"
                ) from e

        except ValueError:
            # Validation error — tidak perlu retry, langsung raise
            raise

        except Exception as e:
            last_error = e
            logger.error(f"Unexpected error pada attempt {attempt}: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BASE_DELAY)
            else:
                raise RuntimeError(
                    f"LLM call gagal setelah {MAX_RETRIES} attempt.\n"
                    f"Model: {model}\n"
                    f"Error: {e}"
                ) from e

    # Seharusnya tidak sampai sini, tapi safety net
    raise RuntimeError(
        f"LLM call gagal setelah {MAX_RETRIES} attempt. Last error: {last_error}"
    )
