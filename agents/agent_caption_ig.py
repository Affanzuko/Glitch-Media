"""
agents/agent_caption_ig.py
Node 3b — Agent Caption IG.
Generate caption singkat untuk Instagram berdasarkan berita yang sudah difilter.
"""

import json
import logging

from tools.llm_client import call_llm
from config.schemas import FilteredData, CaptionIG
from config.settings import load_prompt, AGENT_CAPTION_IG_MODEL

logger = logging.getLogger(__name__)

def run(filtered_data: FilteredData) -> CaptionIG:
    """
    Jalankan Agent Caption IG — buat caption singkat untuk Instagram.

    Args:
        filtered_data: FilteredData dari Agent Screening.

    Returns:
        CaptionIG berisi caption singkat untuk posting di Instagram.
    """
    logger.info(f"Agent Caption IG: membuat caption dari {len(filtered_data.items)} item")

    if not filtered_data.items:
        logger.warning("Agent Caption IG: tidak ada item untuk dibuatkan caption!")
        return CaptionIG(
            news_ref_title="(Tidak ada berita)",
            caption_short="Tidak ada berita gaming terbaru saat ini.",
        )

    # Load system prompt
    system_prompt = load_prompt("caption_ig_prompt.md")

    # Siapkan data item yang sudah difilter
    items_data = []
    for item in filtered_data.items:
        items_data.append({
            "title": item.title,
            "summary": item.summary,
            "source": item.source,
            "url": item.url,
            "quality_score": item.quality_score,
        })

    user_message = (
        f"Berikut adalah {len(items_data)} berita gaming yang sudah lolos screening. "
        f"Pilih 1 berita terbaik dan buatkan caption untuk Instagram.\n\n"
        f"Data:\n{json.dumps(items_data, ensure_ascii=False, indent=2)}"
    )

    # Panggil LLM dengan schema enforcement
    result = call_llm(
        system_prompt=system_prompt,
        user_message=user_message,
        response_schema=CaptionIG,
        model=AGENT_CAPTION_IG_MODEL,
    )

    logger.info(f"Agent Caption IG: caption dibuat untuk '{result.news_ref_title}'")
    return result
