"""
tools/scrapers/gaming_site_scraper.py
Scraper untuk situs berita gaming — menggunakan RSS feeds + BeautifulSoup.
"""

import logging
from datetime import datetime, timezone

from config.settings import GAMING_NEWS_FEEDS
from config.schemas import RawItem

logger = logging.getLogger(__name__)


def _parse_feed(feed_url: str, max_entries: int = 10) -> list[RawItem]:
    """Parse satu RSS feed dan kembalikan list RawItem."""
    items: list[RawItem] = []

    try:
        import feedparser

        feed = feedparser.parse(feed_url)

        if feed.bozo and not feed.entries:
            logger.warning(f"Gaming Sites: feed error for {feed_url}: {feed.bozo_exception}")
            return items

        for entry in feed.entries[:max_entries]:
            # Ambil konten dari summary atau content
            content = ""
            if hasattr(entry, "summary"):
                content = entry.summary
            elif hasattr(entry, "content"):
                content = entry.content[0].value if entry.content else ""

            # Bersihkan HTML tags dari konten
            if content:
                from bs4 import BeautifulSoup

                soup = BeautifulSoup(content, "html.parser")
                content = soup.get_text(separator=" ", strip=True)

            # Parse tanggal publish
            published = datetime.now(timezone.utc)
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                except (TypeError, ValueError):
                    pass

            item = RawItem(
                source="gaming_news",
                title=entry.get("title", "Untitled"),
                content=content[:2000] if content else entry.get("title", ""),
                url=entry.get("link", feed_url),
                scraped_at=published,
            )
            items.append(item)

    except Exception as e:
        logger.warning(f"Gaming Sites: gagal parse feed {feed_url}: {e}")

    return items


def _scrape_page(url: str) -> str:
    """Scrape konten teks dari halaman web (fallback jika RSS tidak tersedia)."""
    try:
        import requests
        from bs4 import BeautifulSoup

        response = requests.get(url, timeout=10, headers={
            "User-Agent": "Mozilla/5.0 (compatible; GlitchMediaBot/1.0)"
        })
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Hapus script dan style tags
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        return soup.get_text(separator=" ", strip=True)[:3000]

    except Exception as e:
        logger.warning(f"Gaming Sites: gagal scrape page {url}: {e}")
        return ""


def scrape(max_entries_per_feed: int = 10) -> list[RawItem]:
    """
    Scrape berita gaming dari RSS feeds yang dikonfigurasi.

    Args:
        max_entries_per_feed: Jumlah entry per feed.

    Returns:
        List of RawItem dari situs berita gaming.
    """
    all_items: list[RawItem] = []

    for feed_url in GAMING_NEWS_FEEDS:
        items = _parse_feed(feed_url, max_entries=max_entries_per_feed)
        all_items.extend(items)
        logger.info(f"Gaming Sites: scraped {len(items)} articles from {feed_url}")

    return all_items
