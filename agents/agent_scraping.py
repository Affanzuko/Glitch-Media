"""
agents/agent_scraping.py
Node 1 — Agent Scraping.
Mengumpulkan berita gaming dari berbagai sumber dan mengembalikan RawData.
"""

import logging
from datetime import datetime, timezone

from config.schemas import RawData, RawItem
from tools.scrapers import (
    reddit_scraper,
    twitter_scraper,
    steam_news_scraper,
    gaming_site_scraper,
)

logger = logging.getLogger(__name__)

# Mapping nama sumber → module scraper
SCRAPER_REGISTRY: dict = {
    "reddit": reddit_scraper,
    "twitter": twitter_scraper,
    "steam": steam_news_scraper,
    "gaming_news": gaming_site_scraper,
}


def run(sources: list[str]) -> RawData:
    """
    Jalankan Agent Scraping — kumpulkan berita dari sumber yang diberikan.

    Args:
        sources: List nama sumber (mis. ["reddit", "twitter", "steam"]).

    Returns:
        RawData berisi semua item berita mentah dari semua sumber.
    """
    logger.info(f"Agent Scraping: memulai scraping dari {len(sources)} sumber: {sources}")

    all_items: list[RawItem] = []

    for source_name in sources:
        scraper_mod = SCRAPER_REGISTRY.get(source_name)

        if scraper_mod is None:
            logger.warning(f"Agent Scraping: sumber '{source_name}' tidak dikenal, dilewati.")
            continue

        try:
            logger.info(f"Agent Scraping: scraping dari '{source_name}'...")
            items = scraper_mod.scrape()
            all_items.extend(items)
            logger.info(f"Agent Scraping: dapat {len(items)} item dari '{source_name}'")

        except Exception as e:
            # Kegagalan satu sumber tidak menghentikan sumber lain
            logger.error(f"Agent Scraping: error scraping '{source_name}': {e}")
            continue

    logger.info(f"Agent Scraping: total {len(all_items)} item dari semua sumber.")

    # Jika tidak ada item sama sekali, kembalikan RawData kosong
    if not all_items:
        logger.warning("Agent Scraping: tidak ada item yang berhasil di-scrape!")

    return RawData(items=all_items)
