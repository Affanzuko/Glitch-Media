"""
tools/scrapers/twitter_scraper.py
Scraper untuk Twitter/X — menggunakan Twitter API v2 via tweepy.
"""

import logging
from datetime import datetime, timezone

from config.settings import TWITTER_BEARER_TOKEN
from config.schemas import RawItem

logger = logging.getLogger(__name__)

# Query pencarian berita gaming di Twitter
GAMING_SEARCH_QUERIES: list[str] = [
    "gaming news -is:retweet lang:en",
    "game release -is:retweet lang:en",
    "game update patch -is:retweet lang:en",
]


def _build_client():
    """Buat instance Tweepy Client (API v2)."""
    import tweepy

    return tweepy.Client(bearer_token=TWITTER_BEARER_TOKEN)


def scrape(max_results_per_query: int = 10) -> list[RawItem]:
    """
    Scrape tweet terbaru tentang gaming news.

    Args:
        max_results_per_query: Jumlah tweet per query (min 10, max 100 untuk API v2).

    Returns:
        List of RawItem dari Twitter.
    """
    items: list[RawItem] = []

    try:
        client = _build_client()

        for query in GAMING_SEARCH_QUERIES:
            try:
                response = client.search_recent_tweets(
                    query=query,
                    max_results=max(10, min(max_results_per_query, 100)),
                    tweet_fields=["created_at", "text", "author_id"],
                    expansions=["author_id"],
                )

                if response.data is None:
                    logger.info(f"Twitter: no results for query '{query}'")
                    continue

                for tweet in response.data:
                    item = RawItem(
                        source="twitter",
                        title=tweet.text[:100],  # Twitter tidak punya judul, pakai awal teks
                        content=tweet.text,
                        url=f"https://twitter.com/i/status/{tweet.id}",
                        scraped_at=datetime.now(timezone.utc),
                    )
                    items.append(item)

                logger.info(
                    f"Twitter: scraped {len(response.data)} tweets for query '{query}'"
                )

            except Exception as e:
                logger.warning(f"Twitter: gagal query '{query}': {e}")
                continue

    except Exception as e:
        logger.error(f"Twitter: gagal inisialisasi client: {e}")

    return items
