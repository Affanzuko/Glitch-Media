"""
agents/agent_screening.py
Node 2 — Agent Screening.
Filter berita mentah: deduplikasi + quality scoring via LLM.
"""

import json
import logging

from tools.llm_client import call_llm
from config.schemas import RawData, FilteredData, FilteredItem
from config.settings import load_prompt, QUALITY_THRESHOLD, AGENT_SCREENING_MODEL

logger = logging.getLogger(__name__)


def run(raw_data: RawData) -> FilteredData:
    """
    Jalankan Agent Screening — filter dan nilai kualitas berita mentah.

    Args:
        raw_data: RawData dari Agent Scraping.

    Returns:
        FilteredData berisi item yang lolos screening (quality >= threshold, bukan duplikat).
    """
    logger.info(f"Agent Screening: memproses {len(raw_data.items)} item mentah")

    if not raw_data.items:
        logger.warning("Agent Screening: tidak ada item untuk di-screen!")
        return FilteredData(items=[])

    # Load system prompt
    system_prompt = load_prompt("screening_prompt.md")

    # Siapkan data untuk LLM
    items_data = []
    for item in raw_data.items:
        items_data.append({
            "title": item.title,
            "content": item.content[:500],  # Truncate untuk hemat token
            "source": item.source,
            "url": item.url,
        })

    user_message = (
        f"Berikut adalah {len(items_data)} item berita mentah yang perlu di-screen.\n\n"
        f"Quality threshold: {QUALITY_THRESHOLD}\n\n"
        f"Data:\n{json.dumps(items_data, ensure_ascii=False, indent=2)}"
    )

    # Panggil LLM dengan schema enforcement
    result = call_llm(
        system_prompt=system_prompt,
        user_message=user_message,
        response_schema=FilteredData,
        model=AGENT_SCREENING_MODEL,
    )

    # Post-processing: filter berdasarkan threshold dan duplikat
    filtered_items: list[FilteredItem] = [
        item for item in result.items
        if item.quality_score >= QUALITY_THRESHOLD and not item.is_duplicate
    ]

    logger.info(
        f"Agent Screening: {len(filtered_items)}/{len(raw_data.items)} item lolos "
        f"(threshold={QUALITY_THRESHOLD})"
    )

    return FilteredData(items=filtered_items)
