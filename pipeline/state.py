"""
pipeline/state.py
Dataclass PipelineState — state object tunggal yang mengalir di sepanjang pipeline.

Mengikuti pola common/shared state pada sequential orchestration:
satu objek yang membawa hasil setiap tahap, sehingga proses bisa di-checkpoint
tepat sebelum gate HITL (tahap 5) dan di-resume tanpa mengulang tahap 1–4.
"""

from dataclasses import dataclass, field

from config.schemas import (
    RawData,
    FilteredData,
    CaptionX,
    CaptionIG,
    ImageGenResult,
    ValidationResult,
)


@dataclass
class PipelineState:
    """
    State object tunggal yang mengalir di seluruh pipeline.

    Attributes:
        raw_data: Output Agent Scraping (Node 1).
        filtered_data: Output Agent Screening (Node 2).
        caption_x: Output Agent Caption X (Node 3a).
        caption_ig: Output Agent Caption IG (Node 3b).
        image_result: Output Agent Image Generation (Node 4).
        validation: Output Validasi User (Node 5).
        run_id: Unique identifier untuk setiap eksekusi pipeline.
        logs: Log messages selama eksekusi.
    """
    raw_data: RawData | None = None
    filtered_data: FilteredData | None = None
    caption_x: CaptionX | None = None
    caption_ig: CaptionIG | None = None
    image_result: ImageGenResult | None = None
    validation: ValidationResult | None = None
    run_id: str = ""
    logs: list[str] = field(default_factory=list)
