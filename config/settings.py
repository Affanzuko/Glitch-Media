"""
config/settings.py
Load .env, API keys, model name, konstanta.
Semua konfigurasi terpusat di sini — modul lain mengimpor dari sini.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ── Paths ────────────────────────────────────────────────────────────────────
# Root project = parent dari folder config/
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Load .env dari root project
load_dotenv(PROJECT_ROOT / ".env")

# ── LLM ──────────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
LLM_MODEL: str = os.getenv("LLM_MODEL", "claude-sonnet-4-20250514")
LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "4096"))
LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.4"))

# ── Image Generation ─────────────────────────────────────────────────────────
IMAGE_GEN_API_KEY: str = os.getenv("IMAGE_GEN_API_KEY", "")
IMAGE_GEN_PROVIDER: str = os.getenv("IMAGE_GEN_PROVIDER", "openai")  # openai | stability | replicate
IMAGE_GEN_MODEL: str = os.getenv("IMAGE_GEN_MODEL", "dall-e-3")

# ── Twitter / X API ──────────────────────────────────────────────────────────
TWITTER_API_KEY: str = os.getenv("TWITTER_API_KEY", "")
TWITTER_API_SECRET: str = os.getenv("TWITTER_API_SECRET", "")
TWITTER_ACCESS_TOKEN: str = os.getenv("TWITTER_ACCESS_TOKEN", "")
TWITTER_ACCESS_SECRET: str = os.getenv("TWITTER_ACCESS_SECRET", "")
TWITTER_BEARER_TOKEN: str = os.getenv("TWITTER_BEARER_TOKEN", "")

# ── Instagram Graph API ──────────────────────────────────────────────────────
INSTAGRAM_ACCESS_TOKEN: str = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
INSTAGRAM_BUSINESS_ACCOUNT_ID: str = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "")

# ── Reddit API ────────────────────────────────────────────────────────────────
REDDIT_CLIENT_ID: str = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET: str = os.getenv("REDDIT_CLIENT_SECRET", "")
REDDIT_USER_AGENT: str = os.getenv("REDDIT_USER_AGENT", "glitch-media-agent/1.0")

# ── YouTube Data API ─────────────────────────────────────────────────────────
YOUTUBE_API_KEY: str = os.getenv("YOUTUBE_API_KEY", "")

# ── Steam Web API ─────────────────────────────────────────────────────────────
STEAM_API_KEY: str = os.getenv("STEAM_API_KEY", "")

# ── Data & Log Paths ─────────────────────────────────────────────────────────
DATA_DIR: Path = PROJECT_ROOT / "data"
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
    "youtube",
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
    730,     # CS2
    570,     # Dota 2
    440,     # TF2
    1172470, # Apex Legends
    1245620, # Elden Ring
]


def load_prompt(filename: str) -> str:
    """Load isi file prompt dari config/prompts/."""
    prompt_path = PROMPTS_DIR / filename
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
    return prompt_path.read_text(encoding="utf-8")
