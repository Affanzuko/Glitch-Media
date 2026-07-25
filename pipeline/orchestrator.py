"""
pipeline/orchestrator.py
Logic "urutan siapa manggil siapa" — dipisahkan dari agent.
main.ipynb hanya memanggil fungsi-fungsi di sini (notebook = entry point, bukan tempat logic).

Setiap fungsi:
- Menerima PipelineState
- Menjalankan agent yang sesuai
- Menyimpan intermediate output ke data/
- Mengembalikan PipelineState yang sudah diperbarui
"""

import json
import logging
import random
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from agents import (
    agent_scraping,
    agent_screening,
    agent_caption_x,
    agent_caption_ig,
    agent_image_generation,
    agent_upload_x,
    agent_upload_ig,
)
from config.settings import (
    RAW_DIR,
    FILTERED_DIR,
    CAPTIONS_DIR,
    DATA_DIR,
)
from pipeline.state import PipelineState

logger = logging.getLogger(__name__)


def _save_json(data, directory: Path, run_id: str, name: str) -> Path:
    """Simpan data Pydantic sebagai JSON ke folder output."""
    directory.mkdir(parents=True, exist_ok=True)
    filepath = directory / f"{run_id}_{name}.json"

    if hasattr(data, "model_dump_json"):
        filepath.write_text(data.model_dump_json(indent=2), encoding="utf-8")
    else:
        filepath.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    logger.info(f"Saved: {filepath}")
    return filepath


def _log(state: PipelineState, message: str) -> None:
    """Tambahkan log message ke state dan Python logger."""
    timestamp = datetime.now(timezone.utc).isoformat()
    entry = f"[{timestamp}] {message}"
    state.logs.append(entry)
    logger.info(message)


# ── Stage 1-2: Scraping + Screening (Sequential) ─────────────────────────────

def run_stage_1_2(state: PipelineState, sources: list[str]) -> PipelineState:
    """
    Tahap 1-2: Scraping → Screening (sequential).

    Args:
        state: PipelineState saat ini.
        sources: List sumber berita (mis. ["reddit", "steam"]).

    Returns:
        PipelineState dengan raw_data dan filtered_data terisi.
    """
    _log(state, f"=== STAGE 1: Scraping ({len(sources)} sources) ===")

    try:
        state.raw_data = agent_scraping.run(sources)
        _save_json(state.raw_data, RAW_DIR, state.run_id, "raw_data")
        _log(state, f"Stage 1 selesai: {len(state.raw_data.items)} raw items")
    except Exception as e:
        _log(state, f"Stage 1 ERROR: {e}")
        raise

    _log(state, "=== STAGE 2: Screening ===")

    try:
        state.filtered_data = agent_screening.run(state.raw_data)
        _save_json(state.filtered_data, FILTERED_DIR, state.run_id, "filtered_data")
        _log(state, f"Stage 2 selesai: {len(state.filtered_data.items)} filtered items")
    except Exception as e:
        _log(state, f"Stage 2 ERROR: {e}")
        raise

    return state


# ── Stage 3: Caption X & IG (Parallel Fork) ──────────────────────────────────

def run_stage_3_fork(state: PipelineState) -> PipelineState:
    """
    Tahap 3: Fork — Caption X dan Caption IG berjalan paralel.

    Caption X dan Caption IG tidak saling bergantung,
    keduanya hanya membutuhkan filtered_data → bisa dieksekusi paralel.

    Args:
        state: PipelineState dengan filtered_data terisi.

    Returns:
        PipelineState dengan caption_x dan caption_ig terisi.
    """
    _log(state, "=== STAGE 3: Caption Fork (X ∥ IG) ===")

    if state.filtered_data is None:
        raise ValueError("Stage 3 membutuhkan filtered_data (jalankan stage 1-2 dulu)")

    # ── LOGIKA PEMILIHAN BERITA (RANDOM & CEK HISTORI) ──
    history_file = DATA_DIR / "history.json"
    history = []
    if history_file.exists():
        try:
            history = json.loads(history_file.read_text(encoding="utf-8"))
        except Exception:
            history = []

    # Filter item yang URL atau judulnya belum ada di history
    available_items = [
        item for item in state.filtered_data.items 
        if item.url not in history and item.title not in history
    ]

    if not available_items:
        _log(state, "⚠️ Semua berita sudah pernah diposting (ada di histori). Mengambil secara acak dari semua data hasil filter sebagai fallback.")
        available_items = state.filtered_data.items

    if not available_items:
        raise ValueError("Tidak ada berita yang tersedia untuk diproses.")

    # Pilih 1 berita secara acak
    selected_item = random.choice(available_items)
    _log(state, f"Berita terpilih (Acak): {selected_item.title}")

    # Simpan ke history
    history.append(selected_item.url)
    history.append(selected_item.title) # Simpan judul juga untuk amannya
    history_file.write_text(json.dumps(history, indent=2), encoding="utf-8")

    # Buat state FilteredData baru yang HANYA berisi 1 berita terpilih
    # agar agen caption X dan IG membuat caption dari berita yang sama
    from config.schemas import FilteredData
    selected_filtered_data = FilteredData(items=[selected_item])

    errors: dict[str, Exception] = {}

    with ThreadPoolExecutor(max_workers=2) as ex:
        # Kirim HANYA 1 berita terpilih ke kedua agen
        fx = ex.submit(agent_caption_x.run, selected_filtered_data)
        fig = ex.submit(agent_caption_ig.run, selected_filtered_data)

        # Ambil hasil Caption X
        try:
            state.caption_x = fx.result()
            _log(state, f"Stage 3a (Caption X): selesai — '{state.caption_x.news_ref_title}'")
        except Exception as e:
            errors["caption_x"] = e
            _log(state, f"Stage 3a (Caption X) ERROR: {e}")

        # Ambil hasil Caption IG — kegagalan Caption X tidak menghentikan Caption IG
        try:
            state.caption_ig = fig.result()
            _log(state, f"Stage 3b (Caption IG): selesai — '{state.caption_ig.news_ref_title}'")
        except Exception as e:
            errors["caption_ig"] = e
            _log(state, f"Stage 3b (Caption IG) ERROR: {e}")

    # Simpan intermediate output
    if state.caption_x:
        _save_json(state.caption_x, CAPTIONS_DIR, state.run_id, "caption_x")
    if state.caption_ig:
        _save_json(state.caption_ig, CAPTIONS_DIR, state.run_id, "caption_ig")

    # Jika kedua-duanya gagal, raise
    if "caption_x" in errors and "caption_ig" in errors:
        raise RuntimeError(
            f"Stage 3 gagal total. X: {errors['caption_x']}, IG: {errors['caption_ig']}"
        )

    return state


# ── Stage 4: Image Generation (Sequential, depends on 3b) ────────────────────

def run_stage_4(state: PipelineState) -> PipelineState:
    """
    Tahap 4: Image Generation — sequential, tergantung pada caption_ig.

    Args:
        state: PipelineState dengan caption_ig terisi.

    Returns:
        PipelineState dengan image_result terisi.
    """
    _log(state, "=== STAGE 4: Image Generation ===")

    if state.caption_ig is None:
        raise ValueError("Stage 4 membutuhkan caption_ig (jalankan stage 3 dulu)")

    try:
        state.image_result = agent_image_generation.run(
            caption_ig=state.caption_ig,
            run_id=state.run_id,
        )
        _log(state, f"Stage 4 selesai: image saved to '{state.image_result.image_path}'")
    except Exception as e:
        _log(state, f"Stage 4 ERROR: {e}")
        raise

    return state


# ── Stage 6: Upload X & IG (Parallel, after HITL gate) ───────────────────────

def run_stage_6_upload(state: PipelineState) -> PipelineState:
    """
    Tahap 6: Upload ke X dan IG secara paralel (setelah ACC di gate HITL).

    Join (dari stage 5 validation) → Split (upload X ∥ upload IG).

    Args:
        state: PipelineState dengan validation.status == "ACC".

    Returns:
        PipelineState (upload results dicatat di logs).
    """
    _log(state, "=== STAGE 6: Upload Fork (X ∥ IG) ===")

    upload_results = {}

    with ThreadPoolExecutor(max_workers=2) as ex:
        futures = {}

        # Submit Upload X jika caption_x tersedia dan di-approve
        if state.caption_x and (
            state.validation is None or state.validation.caption_x_approved
        ):
            futures["x"] = ex.submit(agent_upload_x.run, state.caption_x)
        else:
            _log(state, "Stage 6a (Upload X): dilewati (caption_x tidak tersedia/rejected)")

        # Submit Upload IG jika caption_ig + image tersedia dan di-approve
        if state.caption_ig and state.image_result and (
            state.validation is None
            or (state.validation.caption_ig_approved and state.validation.image_approved)
        ):
            futures["ig"] = ex.submit(
                agent_upload_ig.run, state.caption_ig, state.image_result
            )
        else:
            _log(state, "Stage 6b (Upload IG): dilewati (caption_ig/image tidak tersedia/rejected)")

        # Collect results — kegagalan satu upload tidak menghentikan upload lain
        for platform, future in futures.items():
            try:
                result = future.result()
                upload_results[platform] = result
                _log(
                    state,
                    f"Stage 6 ({platform}): {'sukses' if result.success else 'gagal'} "
                    f"— {result.post_url or result.error}"
                )
            except Exception as e:
                _log(state, f"Stage 6 ({platform}) ERROR: {e}")

    return state
