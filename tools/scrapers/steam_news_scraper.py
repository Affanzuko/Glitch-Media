"""
tools/scrapers/steam_news_scraper.py
Scraper untuk Steam News — menggunakan Steam Web API (ISteamNews).
"""

import logging
from datetime import datetime, timezone

import requests

from config.settings import STEAM_APP_IDS
from config.schemas import RawItem

logger = logging.getLogger(__name__)

# Steam News API endpoint (tidak perlu API key)
STEAM_NEWS_URL = "https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/"


def scrape(count_per_app: int = 5) -> list[RawItem]:
    """
    Scrape berita terbaru dari Steam News untuk app IDs yang dikonfigurasi.

    Args:
        count_per_app: Jumlah berita per game/app.

    Returns:
        List of RawItem dari Steam.
    """
    items: list[RawItem] = []

    for app_id in STEAM_APP_IDS:
        try:
            response = requests.get(
                STEAM_NEWS_URL,
                params={
                    "appid": app_id,
                    "count": count_per_app,
                    "maxlength": 1000,
                    "format": "json",
                },
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()

            news_items = data.get("appnews", {}).get("newsitems", [])

            for news in news_items:
                # Filter hanya berita resmi (bukan community post)
                if news.get("feed_type", 0) == 0:
                    continue

                item = RawItem(
                    source="steam",
                    title=news.get("title", ""),
                    content=news.get("contents", "")[:2000],
                    url=news.get("url", f"https://store.steampowered.com/app/{app_id}"),
                    scraped_at=datetime.now(timezone.utc),
                )
                items.append(item)

            logger.info(f"Steam: scraped {len(news_items)} news for app {app_id}")

        except requests.RequestException as e:
            logger.warning(f"Steam: gagal scrape app {app_id}: {e}")
            continue
        except Exception as e:
            logger.warning(f"Steam: error parsing app {app_id}: {e}")
            continue

    return items
