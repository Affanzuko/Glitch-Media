"""
tools/scrapers/reddit_scraper.py
Scraper untuk Reddit — menggunakan PRAW (Python Reddit API Wrapper).
"""

import logging
from datetime import datetime, timezone

from config.settings import (
    REDDIT_CLIENT_ID,
    REDDIT_CLIENT_SECRET,
    REDDIT_USER_AGENT,
    REDDIT_SUBREDDITS,
)
from config.schemas import RawItem

logger = logging.getLogger(__name__)


def _build_client():
    """Buat instance PRAW Reddit client."""
    import praw

    return praw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent=REDDIT_USER_AGENT,
    )


def scrape(limit_per_sub: int = 10) -> list[RawItem]:
    """
    Scrape hot posts dari subreddit gaming yang dikonfigurasi.

    Args:
        limit_per_sub: Jumlah post per subreddit yang diambil.

    Returns:
        List of RawItem dari Reddit.
    """
    items: list[RawItem] = []

    try:
        reddit = _build_client()

        for sub_name in REDDIT_SUBREDDITS:
            try:
                subreddit = reddit.subreddit(sub_name)
                for post in subreddit.hot(limit=limit_per_sub):
                    # Skip pinned/stickied posts
                    if post.stickied:
                        continue

                    # Gabungkan selftext dan title untuk konten
                    content = post.selftext if post.selftext else post.title
                    if len(content) < 20:
                        content = f"{post.title}. {post.selftext}".strip()

                    item = RawItem(
                        source="reddit",
                        title=post.title,
                        content=content[:2000],  # Truncate konten panjang
                        url=f"https://reddit.com{post.permalink}",
                        scraped_at=datetime.now(timezone.utc),
                    )
                    items.append(item)

                logger.info(f"Reddit: scraped {len(items)} posts from r/{sub_name}")

            except Exception as e:
                logger.warning(f"Reddit: gagal scrape r/{sub_name}: {e}")
                continue

    except Exception as e:
        logger.error(f"Reddit: gagal inisialisasi client: {e}")

    return items
