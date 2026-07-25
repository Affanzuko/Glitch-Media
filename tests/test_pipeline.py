"""
tests/test_pipeline.py
Integration tests untuk orchestrator, PipelineState, dan checkpoint.
"""

import json
import pytest
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

from config.schemas import (
    RawItem,
    RawData,
    FilteredItem,
    FilteredData,
    CaptionX,
    CaptionIG,
    ImageGenResult,
    ValidationResult,
)
from pipeline.state import PipelineState


# ── Test PipelineState ────────────────────────────────────────────────────────

class TestPipelineState:
    """Test PipelineState dataclass."""

    def test_default_state(self):
        """State baru harus memiliki semua field None dan list kosong."""
        state = PipelineState()
        assert state.raw_data is None
        assert state.filtered_data is None
        assert state.caption_x is None
        assert state.caption_ig is None
        assert state.image_result is None
        assert state.validation is None
        assert state.run_id == ""
        assert state.logs == []

    def test_state_with_run_id(self):
        """State harus bisa diinisialisasi dengan run_id."""
        state = PipelineState(run_id="test_run_001")
        assert state.run_id == "test_run_001"

    def test_state_is_mutable(self):
        """State fields harus bisa diisi secara incremental."""
        state = PipelineState(run_id="test")

        # Simulasi stage 1
        state.raw_data = RawData(items=[
            RawItem(
                source="reddit", title="Test", content="Content",
                url="https://example.com", scraped_at=datetime.now(timezone.utc),
            )
        ])
        assert state.raw_data is not None
        assert len(state.raw_data.items) == 1

        # Simulasi stage 2
        state.filtered_data = FilteredData(items=[
            FilteredItem(
                title="Test", summary="Summary", source="reddit",
                url="https://example.com", quality_score=0.9, is_duplicate=False,
            )
        ])
        assert state.filtered_data is not None

    def test_state_logs(self):
        """State harus bisa menampung log messages."""
        state = PipelineState(run_id="test")
        state.logs.append("[2024-01-01T00:00:00Z] Stage 1 started")
        state.logs.append("[2024-01-01T00:00:05Z] Stage 1 completed")
        assert len(state.logs) == 2


# ── Test Checkpoint ───────────────────────────────────────────────────────────

class TestCheckpoint:
    """Test checkpoint save/load untuk pipeline resume."""

    def _create_sample_state(self) -> PipelineState:
        """Buat sample PipelineState yang sudah terisi sampai stage 4."""
        state = PipelineState(run_id="checkpoint_test")

        state.raw_data = RawData(items=[
            RawItem(
                source="steam", title="CS2 Update", content="Big update",
                url="https://store.steampowered.com/news/730",
                scraped_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            )
        ])

        state.filtered_data = FilteredData(items=[
            FilteredItem(
                title="CS2 Update", summary="Update besar CS2",
                source="steam", url="https://store.steampowered.com/news/730",
                quality_score=0.92, is_duplicate=False,
            )
        ])

        state.caption_x = CaptionX(
            news_ref_title="CS2 Update",
            caption_long="🎮 CS2 just dropped a massive update!\n\n#CS2 #Gaming",
        )

        state.caption_ig = CaptionIG(
            news_ref_title="CS2 Update",
            caption_short="🔫 CS2 Update!\n\n#cs2 #gaming",
        )

        state.image_result = ImageGenResult(
            news_ref_title="CS2 Update",
            image_prompt="A dramatic FPS scene...",
            image_path="data/images/test.png",
        )

        state.logs = ["Stage 1 done", "Stage 2 done", "Stage 3 done", "Stage 4 done"]

        return state

    @patch("validation.human_validation.CHECKPOINTS_DIR")
    def test_save_and_load_checkpoint(self, mock_dir, tmp_path):
        """Checkpoint harus bisa disimpan dan di-load kembali identik."""
        mock_dir.__truediv__ = lambda self, x: tmp_path / x
        mock_dir.mkdir = MagicMock()

        # Patch CHECKPOINTS_DIR di tempat yang benar
        with patch("validation.human_validation.CHECKPOINTS_DIR", tmp_path):
            from validation.human_validation import save_checkpoint, load_checkpoint

            state = self._create_sample_state()

            # Save
            save_checkpoint(state)

            # Verify file exists
            checkpoint_file = tmp_path / f"{state.run_id}.json"
            assert checkpoint_file.exists()

            # Load
            restored = load_checkpoint(state.run_id)

            # Verify equality
            assert restored.run_id == state.run_id
            assert len(restored.logs) == len(state.logs)
            assert restored.raw_data is not None
            assert len(restored.raw_data.items) == len(state.raw_data.items)
            assert restored.filtered_data is not None
            assert restored.caption_x is not None
            assert restored.caption_x.caption_long == state.caption_x.caption_long
            assert restored.caption_ig is not None
            assert restored.caption_ig.caption_short == state.caption_ig.caption_short
            assert restored.image_result is not None
            assert restored.image_result.image_path == state.image_result.image_path

    @patch("validation.human_validation.CHECKPOINTS_DIR")
    def test_load_nonexistent_checkpoint(self, mock_dir, tmp_path):
        """Load checkpoint yang tidak ada harus raise FileNotFoundError."""
        with patch("validation.human_validation.CHECKPOINTS_DIR", tmp_path):
            from validation.human_validation import load_checkpoint

            with pytest.raises(FileNotFoundError):
                load_checkpoint("nonexistent_run_id")


# ── Test Orchestrator ─────────────────────────────────────────────────────────

class TestOrchestrator:
    """Test orchestrator functions."""

    @patch("pipeline.orchestrator.agent_screening")
    @patch("pipeline.orchestrator.agent_scraping")
    def test_run_stage_1_2(self, mock_scraping, mock_screening):
        """Stage 1-2 harus mengisi raw_data dan filtered_data."""
        mock_scraping.run.return_value = RawData(items=[
            RawItem(
                source="reddit", title="News", content="C",
                url="https://r.com/1", scraped_at=datetime.now(timezone.utc),
            )
        ])
        mock_screening.run.return_value = FilteredData(items=[
            FilteredItem(
                title="News", summary="S", source="reddit",
                url="https://r.com/1", quality_score=0.9, is_duplicate=False,
            )
        ])

        from pipeline.orchestrator import run_stage_1_2

        state = PipelineState(run_id="test_orchestrator")
        result = run_stage_1_2(state, ["reddit"])

        assert result.raw_data is not None
        assert result.filtered_data is not None
        assert len(result.raw_data.items) == 1
        assert len(result.filtered_data.items) == 1

    @patch("pipeline.orchestrator.agent_caption_ig")
    @patch("pipeline.orchestrator.agent_caption_x")
    def test_run_stage_3_fork_parallel(self, mock_cx, mock_cig):
        """Stage 3 harus menjalankan Caption X dan IG secara paralel."""
        mock_cx.run.return_value = CaptionX(
            news_ref_title="Test", caption_long="Long caption"
        )
        mock_cig.run.return_value = CaptionIG(
            news_ref_title="Test", caption_short="Short"
        )

        from pipeline.orchestrator import run_stage_3_fork

        state = PipelineState(run_id="test")
        state.filtered_data = FilteredData(items=[
            FilteredItem(
                title="Test", summary="S", source="reddit",
                url="https://example.com", quality_score=0.9, is_duplicate=False,
            )
        ])

        result = run_stage_3_fork(state)

        assert result.caption_x is not None
        assert result.caption_ig is not None
        mock_cx.run.assert_called_once()
        mock_cig.run.assert_called_once()

    def test_run_stage_3_fork_requires_filtered_data(self):
        """Stage 3 harus raise error jika filtered_data belum tersedia."""
        from pipeline.orchestrator import run_stage_3_fork

        state = PipelineState(run_id="test")
        # filtered_data = None

        with pytest.raises(ValueError, match="filtered_data"):
            run_stage_3_fork(state)

    @patch("pipeline.orchestrator.agent_caption_ig")
    @patch("pipeline.orchestrator.agent_caption_x")
    def test_run_stage_3_fork_error_isolation(self, mock_cx, mock_cig):
        """Kegagalan satu caption agent tidak menghentikan yang lain."""
        mock_cx.run.side_effect = RuntimeError("Caption X failed!")
        mock_cig.run.return_value = CaptionIG(
            news_ref_title="Test", caption_short="Short"
        )

        from pipeline.orchestrator import run_stage_3_fork

        state = PipelineState(run_id="test")
        state.filtered_data = FilteredData(items=[
            FilteredItem(
                title="Test", summary="S", source="reddit",
                url="https://example.com", quality_score=0.9, is_duplicate=False,
            )
        ])

        # Harus berhasil — Caption IG tetap jalan meski Caption X gagal
        result = run_stage_3_fork(state)
        assert result.caption_x is None  # Failed
        assert result.caption_ig is not None  # Succeeded

    @patch("pipeline.orchestrator.agent_image_generation")
    def test_run_stage_4(self, mock_img):
        """Stage 4 harus mengisi image_result."""
        mock_img.run.return_value = ImageGenResult(
            news_ref_title="Test",
            image_prompt="A scene...",
            image_path="data/images/test.png",
        )

        from pipeline.orchestrator import run_stage_4

        state = PipelineState(run_id="test")
        state.caption_ig = CaptionIG(
            news_ref_title="Test", caption_short="Caption"
        )

        result = run_stage_4(state)
        assert result.image_result is not None
        assert result.image_result.image_path == "data/images/test.png"

    def test_run_stage_4_requires_caption_ig(self):
        """Stage 4 harus raise error jika caption_ig belum tersedia."""
        from pipeline.orchestrator import run_stage_4

        state = PipelineState(run_id="test")
        # caption_ig = None

        with pytest.raises(ValueError, match="caption_ig"):
            run_stage_4(state)
