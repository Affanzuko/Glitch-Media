"""
config/schemas.py
Semua Pydantic schema (kontrak data antar-tahap).

Semua output agent WAJIB berupa objek Pydantic (schema enforcement) —
mencegah tool/data divergence dan memudahkan validasi otomatis
sebelum data diteruskan ke agent berikutnya.
"""

from pydantic import BaseModel
from typing import Literal
from datetime import datetime


class RawItem(BaseModel):
    """Satu item berita mentah hasil scraping."""
    source: Literal["gaming_news", "reddit", "twitter", "youtube", "steam", "other"]
    title: str
    content: str
    url: str
    scraped_at: datetime


class RawData(BaseModel):
    """Kumpulan item berita mentah — output Agent Scraping (Node 1)."""
    items: list[RawItem]


class FilteredItem(BaseModel):
    """Satu item berita yang sudah difilter dan dinilai kualitasnya."""
    title: str
    summary: str
    source: str
    url: str
    quality_score: float          # hasil penilaian Agent Screening
    is_duplicate: bool


class FilteredData(BaseModel):
    """Kumpulan item yang lolos screening — output Agent Screening (Node 2)."""
    items: list[FilteredItem]


class CaptionX(BaseModel):
    """Caption panjang untuk X/Twitter — output Agent Caption X (Node 3a)."""
    news_ref_title: str
    caption_long: str             # caption panjang untuk X


class CaptionIG(BaseModel):
    """Caption singkat untuk Instagram — output Agent Caption IG (Node 3b)."""
    news_ref_title: str
    caption_short: str            # caption singkat untuk IG


class ImageGenResult(BaseModel):
    """Hasil generate gambar — output Agent Image Generation (Node 4)."""
    news_ref_title: str
    image_prompt: str
    image_path: str               # path lokal file gambar hasil generate


class ValidationResult(BaseModel):
    """Keputusan user di gate HITL — output tahap Validasi (Node 5)."""
    news_ref_title: str
    caption_x_approved: bool
    caption_ig_approved: bool
    image_approved: bool
    status: Literal["ACC", "REJECT"]
    reviewer_note: str | None = None


class UploadResult(BaseModel):
    """Hasil upload ke platform — output Agent Upload (Node 6a / 6b)."""
    platform: Literal["x", "instagram"]
    success: bool
    post_url: str | None = None
    error: str | None = None
