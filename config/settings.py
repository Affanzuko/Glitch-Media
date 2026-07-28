"""
config/settings.py
Load .env, API keys, model name, konstanta.
Semua konfigurasi terpusat di sini — modul lain mengimpor dari sini.

Mendukung dua mode integrasi LLM:
  - LOCAL  : via 9Router (proxy lokal, OpenAI-compatible)
  - CLOUD  : via Alibaba Cloud DashScope compatible-mode API
Ditentukan oleh env var LLM_PROVIDER ("local" | "cloud").
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ── Paths ────────────────────────────────────────────────────────────────────
# Root project = parent dari folder config/
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Load .env dari root project
load_dotenv(PROJECT_ROOT / ".env")

# ── LLM Provider Mode ────────────────────────────────────────────────────────
# "local"  → pakai 9Router (development)
# "cloud"  → pakai Alibaba Cloud DashScope API (production / deployment)
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "local").strip().lower()

# ── 9Router (Local AI Router - OpenAI-compatible) ───────────────────────────
NINEROUTER_BASE_URL: str = os.getenv("NINEROUTER_BASE_URL", "")

# ── Alibaba Cloud DashScope (Production API) ────────────────────────────────
DASHSCOPE_API_KEY: str = os.getenv("DASHSCOPE_API_KEY", "")
DASHSCOPE_BASE_URL: str = os.getenv(
    "DASHSCOPE_BASE_URL",
    "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
)

# ── Per-Agent Model Configuration ────────────────────────────────────────────
# Model ID untuk mode LOCAL (9Router proxy)
AGENT_SCRAPING_MODEL_LOCAL: str = os.getenv("AGENT_SCRAPING_MODEL_LOCAL", "ag/gemini-pro-agent")
AGENT_SCREENING_MODEL_LOCAL: str = os.getenv("AGENT_SCREENING_MODEL_LOCAL", "kr/glm-5")
AGENT_CAPTION_X_MODEL_LOCAL: str = os.getenv("AGENT_CAPTION_X_MODEL_LOCAL", "ag/gemini-3.1-pro-low")
AGENT_CAPTION_IG_MODEL_LOCAL: str = os.getenv("AGENT_CAPTION_IG_MODEL_LOCAL", "ag/gemini-3.1-pro-low")
AGENT_IMAGE_GEN_MODEL_LOCAL: str = os.getenv("AGENT_IMAGE_GEN_MODEL_LOCAL", "ag/gemini-pro-agent")

# Model ID untuk mode CLOUD (DashScope — Alibaba Cloud)
# Daftar model: https://www.alibabacloud.com/help/en/model-studio/getting-started/models
AGENT_SCRAPING_MODEL_CLOUD: str = os.getenv("AGENT_SCRAPING_MODEL_CLOUD", "qwen-plus")
AGENT_SCREENING_MODEL_CLOUD: str = os.getenv("AGENT_SCREENING_MODEL_CLOUD", "deepseek-r1")
AGENT_CAPTION_X_MODEL_CLOUD: str = os.getenv("AGENT_CAPTION_X_MODEL_CLOUD", "qwen-plus")
AGENT_CAPTION_IG_MODEL_CLOUD: str = os.getenv("AGENT_CAPTION_IG_MODEL_CLOUD", "qwen-plus")
AGENT_IMAGE_GEN_MODEL_CLOUD: str = os.getenv("AGENT_IMAGE_GEN_MODEL_CLOUD", "qwen-plus")

# Per-Agent Fallback Chain — urutan model cadangan per agent
# Dicoba satu per satu dari kiri ke kanan jika model utama gagal.
_AGENT_NAMES = ["caption_x", "caption_ig", "screening", "scraping", "image_gen"]

def _parse_chain(env_key: str, default: str) -> list[str]:
    return [m.strip() for m in os.getenv(env_key, default).split(",") if m.strip()]

AGENT_FALLBACK_CHAINS_LOCAL: dict[str, list[str]] = {
    name: _parse_chain(f"AGENT_FALLBACK_{name.upper()}_LOCAL", "kr/glm-5")
    for name in _AGENT_NAMES
}
AGENT_FALLBACK_CHAINS_CLOUD: dict[str, list[str]] = {
    "caption_x":  _parse_chain("AGENT_FALLBACK_CAPTION_X_CLOUD", "qwen-max,glm-4-plus"),
    "caption_ig": _parse_chain("AGENT_FALLBACK_CAPTION_IG_CLOUD", "qwen-max,glm-4-plus"),
    "screening":  _parse_chain("AGENT_FALLBACK_SCREENING_CLOUD", "deepseek-v3,glm-4-plus"),
    "scraping":   _parse_chain("AGENT_FALLBACK_SCRAPING_CLOUD", "qwen-max,glm-4-plus"),
    "image_gen":  _parse_chain("AGENT_FALLBACK_IMAGE_GEN_CLOUD", "qwen-max,glm-4-plus"),
}

# Image generation model fallback chain (bukan LLM, tapi image gen API)
IMAGE_GEN_MODEL_CHAIN: list[str] = _parse_chain(
    "IMAGE_GEN_MODEL_CHAIN", "wan2.7-image-pro,qwen-image-3.0-pro"
)


def get_model_for_agent(agent_name: str) -> str:
    """
    Ambil model ID yang sesuai berdasarkan LLM_PROVIDER dan nama agent.

    Args:
        agent_name: Salah satu dari "scraping", "screening", "caption_x",
                    "caption_ig", "image_gen".

    Returns:
        Model ID string yang siap dipakai oleh llm_client.
    """
    model_map_local = {
        "scraping": AGENT_SCRAPING_MODEL_LOCAL,
        "screening": AGENT_SCREENING_MODEL_LOCAL,
        "caption_x": AGENT_CAPTION_X_MODEL_LOCAL,
        "caption_ig": AGENT_CAPTION_IG_MODEL_LOCAL,
        "image_gen": AGENT_IMAGE_GEN_MODEL_LOCAL,
    }
    model_map_cloud = {
        "scraping": AGENT_SCRAPING_MODEL_CLOUD,
        "screening": AGENT_SCREENING_MODEL_CLOUD,
        "caption_x": AGENT_CAPTION_X_MODEL_CLOUD,
        "caption_ig": AGENT_CAPTION_IG_MODEL_CLOUD,
        "image_gen": AGENT_IMAGE_GEN_MODEL_CLOUD,
    }

    if LLM_PROVIDER == "cloud":
        return model_map_cloud.get(agent_name, "qwen-turbo")
    else:
        return model_map_local.get(agent_name, "kr/glm-5")


def get_fallback_chain(agent_name: str = "caption_x") -> list[str]:
    """
    Ambil fallback chain per agent berdasarkan provider aktif.

    Args:
        agent_name: Nama agent (caption_x, caption_ig, screening, scraping, image_gen).

    Returns:
        List model ID yang akan dicoba berurutan jika model utama gagal.
    """
    if LLM_PROVIDER == "cloud":
        return AGENT_FALLBACK_CHAINS_CLOUD.get(agent_name, [])
    return AGENT_FALLBACK_CHAINS_LOCAL.get(agent_name, [])


# ── Backward-compatible aliases (agar agent lama tetap jalan) ────────────────
AGENT_SCRAPING_MODEL: str = get_model_for_agent("scraping")
AGENT_SCREENING_MODEL: str = get_model_for_agent("screening")
AGENT_CAPTION_X_MODEL: str = get_model_for_agent("caption_x")
AGENT_CAPTION_IG_MODEL: str = get_model_for_agent("caption_ig")
AGENT_IMAGE_GEN_MODEL: str = get_model_for_agent("image_gen")

LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "10000"))
LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.4"))

# ── Image Generation ────────────────────────────────────────────────────────
IMAGE_GEN_MODEL: str = os.getenv("IMAGE_GEN_MODEL")
IMAGE_GEN_API_KEY: str = os.getenv("IMAGE_GEN_API_KEY")
IMAGE_GEN_DASHSCOPE_URL: str = os.getenv("IMAGE_GEN_DASHSCOPE_URL")

# ── Twitter / X API ──────────────────────────────────────────────────────────
TWITTER_API_KEY: str = os.getenv("TWITTER_API_KEY", "")
TWITTER_API_SECRET: str = os.getenv("TWITTER_API_SECRET", "")
TWITTER_ACCESS_TOKEN: str = os.getenv("TWITTER_ACCESS_TOKEN", "")
TWITTER_ACCESS_SECRET: str = os.getenv("TWITTER_ACCESS_SECRET", "")
TWITTER_BEARER_TOKEN: str = os.getenv("TWITTER_BEARER_TOKEN", "")

# ── Twitter / X OAuth 2.0 (User login via browser) ──────────────────────────
X_OAUTH_CLIENT_ID: str = os.getenv("X_OAUTH_CLIENT_ID", "")
X_OAUTH_CLIENT_SECRET: str = os.getenv("X_OAUTH_CLIENT_SECRET", "")
X_OAUTH_REDIRECT_URI: str = os.getenv("X_OAUTH_REDIRECT_URI", "http://127.0.0.1:9274/callback/x")

# ── Instagram Graph API ──────────────────────────────────────────────────────
INSTAGRAM_ACCESS_TOKEN: str = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
INSTAGRAM_BUSINESS_ACCOUNT_ID: str = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "")

# ── Instagram OAuth (Facebook Login) ─────────────────────────────────────────
IG_OAUTH_APP_ID: str = os.getenv("IG_OAUTH_APP_ID", "")
IG_OAUTH_APP_SECRET: str = os.getenv("IG_OAUTH_APP_SECRET", "")
IG_OAUTH_REDIRECT_URI: str = os.getenv("IG_OAUTH_REDIRECT_URI", "http://127.0.0.1:9274/callback/ig")

# ── OAuth Server ─────────────────────────────────────────────────────────────
OAUTH_SERVER_PORT: int = int(os.getenv("OAUTH_SERVER_PORT", "9274"))

# ── Reddit API ────────────────────────────────────────────────────────────────
REDDIT_CLIENT_ID: str = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET: str = os.getenv("REDDIT_CLIENT_SECRET", "")
REDDIT_USER_AGENT: str = os.getenv("REDDIT_USER_AGENT", "glitch-media-agent/1.0")

# ── Steam Web API ─────────────────────────────────────────────────────────────
STEAM_API_KEY: str = os.getenv("STEAM_API_KEY", "")

# ── Data & Log Paths ─────────────────────────────────────────────────────────
DATA_DIR: Path = PROJECT_ROOT / "data"
OAUTH_TOKENS_FILE: Path = DATA_DIR / "oauth_tokens.json"
RAW_DIR: Path = DATA_DIR / "raw"
FILTERED_DIR: Path = DATA_DIR / "filtered"
CAPTIONS_DIR: Path = DATA_DIR / "captions"
IMAGES_DIR: Path = DATA_DIR / "images"
CHECKPOINTS_DIR: Path = DATA_DIR / "checkpoints"
LOGS_DIR: Path = PROJECT_ROOT / "logs"
LOG_FILE: Path = LOGS_DIR / "pipeline.log"
PROMPTS_DIR: Path = PROJECT_ROOT / "config" / "prompts"

# ── Retry & Budget ────────────────────────────────────────────────────────────
MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
RETRY_BASE_DELAY: float = float(os.getenv("RETRY_BASE_DELAY", "1.0"))  # seconds
RETRY_MAX_DELAY: float = float(os.getenv("RETRY_MAX_DELAY", "30.0"))   # seconds

# ── Screening ─────────────────────────────────────────────────────────────────
QUALITY_THRESHOLD: float = float(os.getenv("QUALITY_THRESHOLD", "0.6"))

# ── News Sources (default) ────────────────────────────────────────────────────
DEFAULT_SOURCES: list[str] = [
    "reddit",
    "twitter",
    "steam",
    "gaming_news",
]

# ── Subreddit targets for Reddit scraper ──────────────────────────────────────
REDDIT_SUBREDDITS: list[str] = [
    "gaming",
    "Games",
    "pcgaming",
    "PS5",
    "XboxSeriesX",
    "NintendoSwitch",
]

# ── Gaming news RSS feeds ─────────────────────────────────────────────────────
GAMING_NEWS_FEEDS: list[str] = [
    "https://www.ign.com/articles?feeds=ign-all",
    "https://www.gamespot.com/feeds/mashup/",
    "https://kotaku.com/rss",
]

# ── Steam App IDs to monitor ──────────────────────────────────────────────────
STEAM_APP_IDS: list[int] = [
    570,     # Dota 2
    440,     # TF2
    730,     # CS2
    1172470, # Apex Legends
    1245620, # Elden Ring
]

def load_prompt(filename: str) -> str:
    """Load isi file prompt dari config/prompts/."""
    prompt_path = PROMPTS_DIR / filename
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
    return prompt_path.read_text(encoding="utf-8")
