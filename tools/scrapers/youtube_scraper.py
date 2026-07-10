"""
tools/scrapers/youtube_scraper.py
Scraper untuk YouTube — menggunakan YouTube Data API v3.
"""

import logging
from datetime import datetime, timezone

from config.settings import YOUTUBE_API_KEY
from config.schemas import RawItem

logger = logging.getLogger(__name__)

# Channel IDs dan search queries untuk gaming news
GAMING_SEARCH_TERMS: list[str] = [
    "gaming news today",
    "new game release 2025",
    "game update",
]


def _build_client():
    """Buat instance YouTube Data API client."""
    from googleapiclient.discovery import build

    return build("youtube", "v3", developerKey=YOUTUBE_API_KEY)


def scrape(max_results_per_query: int = 5) -> list[RawItem]:
    """
    Scrape video YouTube terbaru tentang gaming news.

    Args:
        max_results_per_query: Jumlah video per search query.

    Returns:
        List of RawItem dari YouTube.
    """
    items: list[RawItem] = []

    try:
        youtube = _build_client()

        for query in GAMING_SEARCH_TERMS:
            try:
                search_response = (
                    youtube.search()
                    .list(
                        q=query,
                        part="snippet",
                        type="video",
                        order="date",
                        maxResults=max_results_per_query,
                        relevanceLanguage="en",
                    )
                    .execute()
                )

                for result in search_response.get("items", []):
                    snippet = result["snippet"]
                    video_id = result["id"]["videoId"]

                    item = RawItem(
                        source="youtube",
                        title=snippet["title"],
                        content=snippet.get("description", snippet["title"])[:2000],
                        url=f"https://www.youtube.com/watch?v={video_id}",
                        scraped_at=datetime.now(timezone.utc),
                    )
                    items.append(item)

                logger.info(
                    f"YouTube: scraped {len(search_response.get('items', []))} "
                    f"videos for query '{query}'"
                )

            except Exception as e:
                logger.warning(f"YouTube: gagal query '{query}': {e}")
                continue

    except Exception as e:
        logger.error(f"YouTube: gagal inisialisasi client: {e}")

    return items
