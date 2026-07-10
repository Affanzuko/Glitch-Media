"""
validation/human_validation.py
Fungsi tampilkan hasil + input ACC/REJECT menggunakan ipywidgets di notebook.

Gate ini WAJIB synchronous — pipeline berhenti total sampai user memberi keputusan.
State disimpan ke data/checkpoints/{run_id}.json sebelum menunggu input,
agar sesi notebook yang terputus tetap bisa di-resume.
"""

import json
import logging
from pathlib import Path
from typing import Any

from IPython.display import display, HTML, Image as IPImage
import ipywidgets as widgets

from config.schemas import ValidationResult
from config.settings import CHECKPOINTS_DIR
from pipeline.state import PipelineState

logger = logging.getLogger(__name__)


def save_checkpoint(state: PipelineState) -> None:
    """
    Simpan PipelineState ke file JSON untuk checkpoint/resume.

    Args:
        state: PipelineState saat ini (sebelum gate HITL).
    """
    CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)
    filepath = CHECKPOINTS_DIR / f"{state.run_id}.json"

    # Serialize state ke dict — handle Pydantic models
    state_dict: dict[str, Any] = {
        "run_id": state.run_id,
        "logs": state.logs,
    }

    if state.raw_data:
        state_dict["raw_data"] = json.loads(state.raw_data.model_dump_json())
    if state.filtered_data:
        state_dict["filtered_data"] = json.loads(state.filtered_data.model_dump_json())
    if state.caption_x:
        state_dict["caption_x"] = json.loads(state.caption_x.model_dump_json())
    if state.caption_ig:
        state_dict["caption_ig"] = json.loads(state.caption_ig.model_dump_json())
    if state.image_result:
        state_dict["image_result"] = json.loads(state.image_result.model_dump_json())
    if state.validation:
        state_dict["validation"] = json.loads(state.validation.model_dump_json())

    filepath.write_text(
        json.dumps(state_dict, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info(f"Checkpoint saved: {filepath}")


def load_checkpoint(run_id: str) -> PipelineState:
    """
    Load PipelineState dari file checkpoint.

    Args:
        run_id: ID run yang ingin di-resume.

    Returns:
        PipelineState yang sudah di-restore dari checkpoint.

    Raises:
        FileNotFoundError: Jika checkpoint tidak ditemukan.
    """
    from config.schemas import (
        RawData, FilteredData, CaptionX, CaptionIG,
        ImageGenResult, ValidationResult,
    )

    filepath = CHECKPOINTS_DIR / f"{run_id}.json"
    if not filepath.exists():
        raise FileNotFoundError(f"Checkpoint tidak ditemukan: {filepath}")

    state_dict = json.loads(filepath.read_text(encoding="utf-8"))
    logger.info(f"Checkpoint loaded: {filepath}")

    state = PipelineState(
        run_id=state_dict.get("run_id", run_id),
        logs=state_dict.get("logs", []),
    )

    if "raw_data" in state_dict:
        state.raw_data = RawData.model_validate(state_dict["raw_data"])
    if "filtered_data" in state_dict:
        state.filtered_data = FilteredData.model_validate(state_dict["filtered_data"])
    if "caption_x" in state_dict:
        state.caption_x = CaptionX.model_validate(state_dict["caption_x"])
    if "caption_ig" in state_dict:
        state.caption_ig = CaptionIG.model_validate(state_dict["caption_ig"])
    if "image_result" in state_dict:
        state.image_result = ImageGenResult.model_validate(state_dict["image_result"])
    if "validation" in state_dict:
        state.validation = ValidationResult.model_validate(state_dict["validation"])

    return state


def request_validation(state: PipelineState) -> ValidationResult:
    """
    Tampilkan hasil pipeline dan minta keputusan ACC/REJECT dari user.
    Menggunakan ipywidgets untuk UI interaktif di notebook.

    Pipeline BERHENTI di sini sampai user menekan tombol.

    Args:
        state: PipelineState dengan caption_x, caption_ig, dan image_result terisi.

    Returns:
        ValidationResult berisi keputusan user.
    """
    import asyncio

    # ── Tampilkan Preview ──────────────────────────────────────────────────

    # Header
    display(HTML(
        "<h2 style='color: #2196F3; border-bottom: 2px solid #2196F3; "
        "padding-bottom: 8px;'>🎮 Validasi Konten — Human-in-the-Loop Gate</h2>"
    ))

    # News title
    news_title = "(Tidak ada berita)"
    if state.caption_x:
        news_title = state.caption_x.news_ref_title
    elif state.caption_ig:
        news_title = state.caption_ig.news_ref_title

    display(HTML(f"<h3>📰 {news_title}</h3>"))

    # Caption X
    if state.caption_x:
        display(HTML(
            "<div style='background: #1a1a2e; color: #fff; padding: 16px; "
            "border-radius: 8px; margin: 8px 0; border-left: 4px solid #1DA1F2;'>"
            f"<b>🐦 Caption X (Twitter)</b><br><br>"
            f"<pre style='white-space: pre-wrap; color: #e0e0e0;'>"
            f"{state.caption_x.caption_long}</pre></div>"
        ))

    # Caption IG
    if state.caption_ig:
        display(HTML(
            "<div style='background: #1a1a2e; color: #fff; padding: 16px; "
            "border-radius: 8px; margin: 8px 0; border-left: 4px solid #E1306C;'>"
            f"<b>📸 Caption IG (Instagram)</b><br><br>"
            f"<pre style='white-space: pre-wrap; color: #e0e0e0;'>"
            f"{state.caption_ig.caption_short}</pre></div>"
        ))

    # Image
    if state.image_result and state.image_result.image_path:
        try:
            display(HTML("<b>🖼️ Generated Image:</b>"))
            display(IPImage(filename=state.image_result.image_path, width=400))
            display(HTML(
                f"<small style='color: #888;'>Prompt: {state.image_result.image_prompt}</small>"
            ))
        except Exception as e:
            display(HTML(f"<p style='color: #f44336;'>⚠️ Gagal menampilkan gambar: {e}</p>"))

    # ── Widget ACC/REJECT ────────────────────────────────────────────────

    # Checkboxes untuk approval granular
    cb_caption_x = widgets.Checkbox(value=True, description="Caption X", indent=False)
    cb_caption_ig = widgets.Checkbox(value=True, description="Caption IG", indent=False)
    cb_image = widgets.Checkbox(value=True, description="Image", indent=False)

    # Note textarea
    note_input = widgets.Textarea(
        placeholder="Catatan reviewer (opsional)...",
        layout=widgets.Layout(width="100%", height="60px"),
    )

    # Buttons
    btn_acc = widgets.Button(
        description="✅ ACC (Approve)",
        button_style="success",
        layout=widgets.Layout(width="200px", height="40px"),
    )
    btn_reject = widgets.Button(
        description="❌ REJECT",
        button_style="danger",
        layout=widgets.Layout(width="200px", height="40px"),
    )

    # Output area for status
    output = widgets.Output()

    # Result container (mutable, untuk diisi oleh callback)
    result_container: dict[str, ValidationResult | None] = {"result": None}

    # Event loop untuk blocking
    loop = asyncio.new_event_loop()
    future = loop.create_future()

    def _on_decision(status: str):
        """Callback saat tombol ditekan."""
        validation = ValidationResult(
            news_ref_title=news_title,
            caption_x_approved=cb_caption_x.value,
            caption_ig_approved=cb_caption_ig.value,
            image_approved=cb_image.value,
            status=status,
            reviewer_note=note_input.value if note_input.value.strip() else None,
        )
        result_container["result"] = validation

        with output:
            if status == "ACC":
                display(HTML(
                    "<p style='color: #4CAF50; font-weight: bold;'>"
                    "✅ Konten di-APPROVE. Melanjutkan ke upload...</p>"
                ))
            else:
                display(HTML(
                    "<p style='color: #f44336; font-weight: bold;'>"
                    "❌ Konten di-REJECT. Pipeline berhenti.</p>"
                ))

        # Disable buttons
        btn_acc.disabled = True
        btn_reject.disabled = True

        # Resolve future
        if not future.done():
            loop.call_soon_threadsafe(future.set_result, validation)

    btn_acc.on_click(lambda _: _on_decision("ACC"))
    btn_reject.on_click(lambda _: _on_decision("REJECT"))

    # Display widgets
    display(HTML("<hr><b>📋 Approval:</b>"))
    display(widgets.HBox([cb_caption_x, cb_caption_ig, cb_image]))
    display(HTML("<b>📝 Catatan:</b>"))
    display(note_input)
    display(widgets.HBox([btn_acc, btn_reject]))
    display(output)

    # Block sampai user klik tombol
    # Menggunakan polling sederhana karena ipywidgets callback
    import time
    while result_container["result"] is None:
        time.sleep(0.5)

    result = result_container["result"]
    state.validation = result

    logger.info(
        f"Validation result: {result.status} "
        f"(X={result.caption_x_approved}, IG={result.caption_ig_approved}, "
        f"Img={result.image_approved})"
    )

    return result
