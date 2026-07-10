"""
tools/llm_client.py
Wrapper panggilan LLM (Claude API via Anthropic SDK).
Mendukung structured output enforcement (JSON → Pydantic parsing).
Retry + exponential backoff + step/attempt budget.
"""

import json
import logging
import time
from typing import TypeVar, Type

from pydantic import BaseModel, ValidationError

from config.settings import (
    ANTHROPIC_API_KEY,
    LLM_MODEL,
    LLM_MAX_TOKENS,
    LLM_TEMPERATURE,
    MAX_RETRIES,
    RETRY_BASE_DELAY,
    RETRY_MAX_DELAY,
)

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Singleton client instance
_client = None


def _get_client():
    """Lazy-init Anthropic client."""
    import anthropic

    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


def call_llm(
    system_prompt: str,
    user_message: str,
    response_schema: Type[T],
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> T:
    """
    Panggil Claude API dengan structured output enforcement.

    Args:
        system_prompt: System prompt untuk LLM.
        user_message: User message (berisi data input).
        response_schema: Pydantic model class untuk parsing response.
        max_tokens: Override max tokens (opsional).
        temperature: Override temperature (opsional).

    Returns:
        Instance dari response_schema yang sudah di-validate.

    Raises:
        RuntimeError: Jika semua retry gagal.
    """
    client = _get_client()
    import anthropic

    tokens = max_tokens or LLM_MAX_TOKENS
    temp = temperature if temperature is not None else LLM_TEMPERATURE

    # Tambahkan instruksi JSON di akhir system prompt
    schema_json = json.dumps(response_schema.model_json_schema(), indent=2)
    enforced_system = (
        f"{system_prompt}\n\n"
        f"## CRITICAL: Response Format\n"
        f"You MUST respond with ONLY a valid JSON object matching this schema:\n"
        f"```json\n{schema_json}\n```\n"
        f"Do NOT include any text before or after the JSON. "
        f"Do NOT wrap in markdown code blocks."
    )

    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(
                f"LLM call attempt {attempt}/{MAX_RETRIES} "
                f"(model={LLM_MODEL}, schema={response_schema.__name__})"
            )

            response = client.messages.create(
                model=LLM_MODEL,
                max_tokens=tokens,
                temperature=temp,
                system=enforced_system,
                messages=[{"role": "user", "content": user_message}],
            )

            # Ekstrak teks response
            raw_text = response.content[0].text.strip()

            # Bersihkan markdown code block jika ada
            if raw_text.startswith("```"):
                lines = raw_text.split("\n")
                # Hapus baris pertama (```json) dan terakhir (```)
                lines = [l for l in lines if not l.strip().startswith("```")]
                raw_text = "\n".join(lines).strip()

            # Parse JSON → Pydantic
            parsed = response_schema.model_validate_json(raw_text)
            logger.info(f"LLM call sukses: {response_schema.__name__}")
            return parsed

        except anthropic.RateLimitError as e:
            last_error = e
            delay = min(RETRY_BASE_DELAY * (2 ** (attempt - 1)), RETRY_MAX_DELAY)
            logger.warning(f"Rate limited, retry in {delay}s: {e}")
            time.sleep(delay)

        except anthropic.APIError as e:
            last_error = e
            delay = min(RETRY_BASE_DELAY * (2 ** (attempt - 1)), RETRY_MAX_DELAY)
            logger.warning(f"API error, retry in {delay}s: {e}")
            time.sleep(delay)

        except (json.JSONDecodeError, ValidationError) as e:
            last_error = e
            logger.warning(
                f"Parse/validation error on attempt {attempt}: {e}. "
                f"Raw response: {raw_text[:200]}..."
            )
            # Retry dengan sedikit delay untuk parsing errors juga
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BASE_DELAY)

        except Exception as e:
            last_error = e
            logger.error(f"Unexpected error on attempt {attempt}: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BASE_DELAY)

    raise RuntimeError(
        f"LLM call gagal setelah {MAX_RETRIES} attempts. "
        f"Schema: {response_schema.__name__}. Last error: {last_error}"
    )


def call_llm_raw(
    system_prompt: str,
    user_message: str,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> str:
    """
    Panggil Claude API tanpa schema enforcement — kembalikan teks mentah.
    Digunakan untuk kasus di mana output bukan JSON (mis. image prompt text).

    Args:
        system_prompt: System prompt untuk LLM.
        user_message: User message.
        max_tokens: Override max tokens (opsional).
        temperature: Override temperature (opsional).

    Returns:
        Response text mentah dari LLM.

    Raises:
        RuntimeError: Jika semua retry gagal.
    """
    client = _get_client()
    import anthropic

    tokens = max_tokens or LLM_MAX_TOKENS
    temp = temperature if temperature is not None else LLM_TEMPERATURE

    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.messages.create(
                model=LLM_MODEL,
                max_tokens=tokens,
                temperature=temp,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
            return response.content[0].text.strip()

        except anthropic.RateLimitError as e:
            last_error = e
            delay = min(RETRY_BASE_DELAY * (2 ** (attempt - 1)), RETRY_MAX_DELAY)
            logger.warning(f"Rate limited, retry in {delay}s: {e}")
            time.sleep(delay)

        except anthropic.APIError as e:
            last_error = e
            delay = min(RETRY_BASE_DELAY * (2 ** (attempt - 1)), RETRY_MAX_DELAY)
            logger.warning(f"API error, retry in {delay}s: {e}")
            time.sleep(delay)

        except Exception as e:
            last_error = e
            logger.error(f"Unexpected error on attempt {attempt}: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BASE_DELAY)

    raise RuntimeError(
        f"LLM raw call gagal setelah {MAX_RETRIES} attempts. Last error: {last_error}"
    )
