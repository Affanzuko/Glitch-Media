"""
tests/test_agents.py
Unit tests per agent — dengan mocked LLM/tool calls.
Memvalidasi input/output schema contracts.
"""

import json
import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from config.schemas import (
    RawItem,
    RawData,
    FilteredItem,
    FilteredData,
    CaptionX,
    CaptionIG,
    ImageGenResult,
    UploadResult,
)


# ── Test Schemas ──────────────────────────────────────────────────────────────

class TestSchemas:
    """Verifikasi bahwa semua Pydantic schemas dapat di-instantiate dengan benar."""

    def test_raw_item(self):
        item = RawItem(
            source="reddit",
            title="Test Gaming News",
            content="Some gaming news content here.",
            url="https://reddit.com/r/gaming/test",
            scraped_at=datetime.now(timezone.utc),
        )
        assert item.source == "reddit"
        assert item.title == "Test Gaming News"

    def test_raw_data(self):
        items = [
            RawItem(
                source="steam",
                title=f"News {i}",
                content=f"Content {i}",
                url=f"https://example.com/{i}",
                scraped_at=datetime.now(timezone.utc),
            )
            for i in range(3)
        ]
        data = RawData(items=items)
        assert len(data.items) == 3

    def test_filtered_item(self):
        item = FilteredItem(
            title="Elden Ring DLC Release",
            summary="DLC baru Elden Ring akan rilis bulan depan.",
            source="gaming_news",
            url="https://example.com/elden-ring",
            quality_score=0.92,
            is_duplicate=False,
        )
        assert item.quality_score == 0.92
        assert not item.is_duplicate

    def test_filtered_data(self):
        data = FilteredData(items=[])
        assert len(data.items) == 0

    def test_caption_x(self):
        caption = CaptionX(
            news_ref_title="Test Title",
            caption_long="This is a long caption for X/Twitter with hashtags #gaming #news",
        )
        assert caption.news_ref_title == "Test Title"
        assert "#gaming" in caption.caption_long

    def test_caption_ig(self):
        caption = CaptionIG(
            news_ref_title="Test Title",
            caption_short="🎮 Short caption!\n\n#gaming",
        )
        assert "🎮" in caption.caption_short

    def test_image_gen_result(self):
        result = ImageGenResult(
            news_ref_title="Test",
            image_prompt="A dramatic scene...",
            image_path="/data/images/test.png",
        )
        assert result.image_path.endswith(".png")

    def test_validation_result_acc(self):
        from config.schemas import ValidationResult

        result = ValidationResult(
            news_ref_title="Test",
            caption_x_approved=True,
            caption_ig_approved=True,
            image_approved=True,
            status="ACC",
        )
        assert result.status == "ACC"
        assert result.reviewer_note is None

    def test_validation_result_reject_with_note(self):
        from config.schemas import ValidationResult

        result = ValidationResult(
            news_ref_title="Test",
            caption_x_approved=False,
            caption_ig_approved=True,
            image_approved=False,
            status="REJECT",
            reviewer_note="Caption X terlalu panjang",
        )
        assert result.status == "REJECT"
        assert result.reviewer_note is not None

    def test_upload_result_success(self):
        result = UploadResult(
            platform="x",
            success=True,
            post_url="https://twitter.com/i/status/12345",
        )
        assert result.success
        assert result.error is None

    def test_upload_result_failure(self):
        result = UploadResult(
            platform="instagram",
            success=False,
            error="API rate limited",
        )
        assert not result.success
        assert result.post_url is None

    def test_schema_json_serialization(self):
        """Verifikasi bahwa semua schema bisa di-serialize ke JSON dan kembali."""
        item = RawItem(
            source="youtube",
            title="Test",
            content="Content",
            url="https://youtube.com/watch?v=test",
            scraped_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        json_str = item.model_dump_json()
        restored = RawItem.model_validate_json(json_str)
        assert restored.source == item.source
        assert restored.title == item.title


# ── Test Agent Scraping ───────────────────────────────────────────────────────

class TestAgentScraping:
    """Test Agent Scraping dengan mocked scrapers."""

    @patch("tools.scrapers.reddit_scraper.scrape")
    def test_run_single_source(self, mock_reddit_scrape):
        """Agent harus bisa scrape dari satu sumber."""
        mock_reddit_scrape.return_value = [
            RawItem(
                source="reddit",
                title="Test Reddit Post",
                content="Some content",
                url="https://reddit.com/test",
                scraped_at=datetime.now(timezone.utc),
            )
        ]

        from agents.agent_scraping import run

        result = run(["reddit"])
        assert isinstance(result, RawData)
        assert len(result.items) == 1
        assert result.items[0].source == "reddit"

    @patch("tools.scrapers.steam_news_scraper.scrape")
    @patch("tools.scrapers.reddit_scraper.scrape")
    def test_run_multiple_sources(self, mock_reddit_scrape, mock_steam_scrape):
        """Agent harus bisa scrape dari beberapa sumber."""
        mock_reddit_scrape.return_value = [
            RawItem(
                source="reddit", title="Reddit", content="C",
                url="https://r.com/1", scraped_at=datetime.now(timezone.utc),
            )
        ]
        mock_steam_scrape.return_value = [
            RawItem(
                source="steam", title="Steam", content="C",
                url="https://s.com/1", scraped_at=datetime.now(timezone.utc),
            )
        ]

        from agents.agent_scraping import run

        # Hanya jalankan reddit dan steam agar tidak bocor ke source lain yang tidak dimock (e.g. youtube/twitter)
        result = run(["reddit", "steam"])
        assert len(result.items) == 2

    def test_run_unknown_source(self):
        """Agent harus melewati sumber yang tidak dikenal tanpa error."""
        from agents.agent_scraping import run

        result = run(["unknown_source"])
        assert isinstance(result, RawData)
        assert len(result.items) == 0

    def test_run_empty_sources(self):
        """Agent harus menangani list sumber kosong."""
        from agents.agent_scraping import run

        result = run([])
        assert isinstance(result, RawData)
        assert len(result.items) == 0


# ── Test Agent Screening ──────────────────────────────────────────────────────

class TestAgentScreening:
    """Test Agent Screening dengan mocked LLM."""

    @patch("agents.agent_screening.call_llm")
    def test_run_filters_by_quality(self, mock_llm):
        """Agent harus memfilter item berdasarkan quality threshold."""
        mock_llm.return_value = FilteredData(items=[
            FilteredItem(
                title="Good News", summary="Summary", source="reddit",
                url="https://example.com", quality_score=0.9, is_duplicate=False,
            ),
            FilteredItem(
                title="Bad News", summary="Summary", source="steam",
                url="https://example.com/2", quality_score=0.3, is_duplicate=False,
            ),
        ])

        raw_data = RawData(items=[
            RawItem(
                source="reddit", title="Good News", content="Content",
                url="https://example.com", scraped_at=datetime.now(timezone.utc),
            ),
        ])

        from agents.agent_screening import run

        result = run(raw_data)
        assert isinstance(result, FilteredData)
        # Hanya item dengan quality >= 0.6 yang lolos
        assert all(item.quality_score >= 0.6 for item in result.items)

    @patch("agents.agent_screening.call_llm")
    def test_run_filters_duplicates(self, mock_llm):
        """Agent harus memfilter item duplikat."""
        mock_llm.return_value = FilteredData(items=[
            FilteredItem(
                title="News", summary="S", source="reddit",
                url="https://example.com", quality_score=0.9, is_duplicate=False,
            ),
            FilteredItem(
                title="Same News", summary="S", source="steam",
                url="https://example.com/2", quality_score=0.8, is_duplicate=True,
            ),
        ])

        raw_data = RawData(items=[
            RawItem(
                source="reddit", title="News", content="C",
                url="https://example.com", scraped_at=datetime.now(timezone.utc),
            ),
        ])

        from agents.agent_screening import run

        result = run(raw_data)
        assert all(not item.is_duplicate for item in result.items)

    def test_run_empty_input(self):
        """Agent harus menangani input kosong."""
        from agents.agent_screening import run

        result = run(RawData(items=[]))
        assert isinstance(result, FilteredData)
        assert len(result.items) == 0


# ── Test Agent Caption X ─────────────────────────────────────────────────────

class TestAgentCaptionX:
    """Test Agent Caption X dengan mocked LLM."""

    @patch("agents.agent_caption_x.call_llm")
    def test_run_generates_caption(self, mock_llm):
        """Agent harus menghasilkan CaptionX dari filtered data."""
        mock_llm.return_value = CaptionX(
            news_ref_title="Elden Ring DLC",
            caption_long="🎮 Elden Ring DLC confirmed!\n\n#EldenRing #Gaming",
        )

        filtered = FilteredData(items=[
            FilteredItem(
                title="Elden Ring DLC", summary="DLC baru confirmed",
                source="gaming_news", url="https://example.com",
                quality_score=0.95, is_duplicate=False,
            ),
        ])

        from agents.agent_caption_x import run

        result = run(filtered)
        assert isinstance(result, CaptionX)
        assert result.news_ref_title == "Elden Ring DLC"
        assert len(result.caption_long) > 0

    def test_run_empty_input(self):
        """Agent harus menangani input kosong tanpa memanggil LLM."""
        from agents.agent_caption_x import run

        result = run(FilteredData(items=[]))
        assert isinstance(result, CaptionX)


# ── Test Agent Caption IG ─────────────────────────────────────────────────────

class TestAgentCaptionIG:
    """Test Agent Caption IG dengan mocked LLM."""

    @patch("agents.agent_caption_ig.call_llm")
    def test_run_generates_caption(self, mock_llm):
        """Agent harus menghasilkan CaptionIG dari filtered data."""
        mock_llm.return_value = CaptionIG(
            news_ref_title="CS2 Update",
            caption_short="🔫 CS2 update besar!\n\n#CS2 #Gaming",
        )

        filtered = FilteredData(items=[
            FilteredItem(
                title="CS2 Update", summary="Update baru CS2",
                source="steam", url="https://example.com",
                quality_score=0.88, is_duplicate=False,
            ),
        ])

        from agents.agent_caption_ig import run

        result = run(filtered)
        assert isinstance(result, CaptionIG)
        assert len(result.caption_short) > 0

    def test_run_empty_input(self):
        """Agent harus menangani input kosong tanpa memanggil LLM."""
        from agents.agent_caption_ig import run

        result = run(FilteredData(items=[]))
        assert isinstance(result, CaptionIG)


# ── Test Agent Upload X ───────────────────────────────────────────────────────

class TestAgentUploadX:
    """Test Agent Upload X dengan mocked API client."""

    @patch("agents.agent_upload_x.post_tweet")
    def test_run_single_tweet(self, mock_post):
        """Agent harus posting tweet singkat sukses."""
        mock_post.return_value = {
            "success": True,
            "post_url": "https://twitter.com/i/status/123",
            "tweet_id": "123",
        }

        caption = CaptionX(
            news_ref_title="Test",
            caption_long="Short tweet under 280 chars.",
        )

        from agents.agent_upload_x import run

        result = run(caption)
        assert isinstance(result, UploadResult)
        assert result.platform == "x"
        assert result.success

    @patch("agents.agent_upload_x.post_tweet")
    def test_run_handles_api_error(self, mock_post):
        """Agent harus menangani error API dan return UploadResult.success=False."""
        mock_post.side_effect = RuntimeError("API Error")

        caption = CaptionX(
            news_ref_title="Test",
            caption_long="Test caption.",
        )

        from agents.agent_upload_x import run

        result = run(caption)
        assert isinstance(result, UploadResult)
        assert not result.success
        assert result.error is not None


# ── Test Agent Upload IG ──────────────────────────────────────────────────────

class TestAgentUploadIG:
    """Test Agent Upload IG dengan mocked API client."""

    @patch("agents.agent_upload_ig.post_image")
    @patch("agents.agent_upload_ig.upload_image_to_hosting")
    def test_run_success(self, mock_upload, mock_post):
        """Agent harus posting ke IG sukses."""
        mock_upload.return_value = "https://hosting.com/image.png"
        mock_post.return_value = {
            "success": True,
            "post_url": "https://instagram.com/p/test/",
            "media_id": "456",
        }

        caption = CaptionIG(news_ref_title="Test", caption_short="Caption")
        image = ImageGenResult(
            news_ref_title="Test",
            image_prompt="prompt",
            image_path="/data/images/test.png",
        )

        from agents.agent_upload_ig import run

        result = run(caption, image)
        assert isinstance(result, UploadResult)
        assert result.platform == "instagram"
        assert result.success
