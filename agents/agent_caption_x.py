"""
agents/agent_caption_x.py
Node 3a — Agent Caption X.
Generate caption panjang untuk X/Twitter berdasarkan berita yang sudah difilter.
"""

import json
import logging

from tools.llm_client import call_llm
from config.schemas import FilteredData, CaptionX
from config.settings import load_prompt, AGENT_CAPTION_X_MODEL

logger = logging.getLogger(__name__)

def run(filtered_data: FilteredData) -> CaptionX:
    """
    Jalankan Agent Caption X — buat caption panjang untuk X/Twitter.

    Args:
        filtered_data: FilteredData dari Agent Screening.

    Returns:
        CaptionX berisi caption panjang untuk posting di X.
    """
    logger.info(f"Agent Caption X: membuat caption dari {len(filtered_data.items)} item")

    if not filtered_data.items:
        logger.warning("Agent Caption X: tidak ada item untuk dibuatkan caption!")
        return CaptionX(
            news_ref_title="(Tidak ada berita)",
            caption_long="Tidak ada berita gaming terbaru saat ini.",
        )

    # Load system prompt
    system_prompt = load_prompt("caption_x_prompt.md")

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
        f"Berikut adalah berita gaming yang telah terpilih. "
        f"Buatkan caption yang menarik untuk X/Twitter berdasarkan berita ini.\n\n"
        f"Data:\n{json.dumps(items_data, ensure_ascii=False, indent=2)}"
    )

    # Panggil LLM dengan schema enforcement
    result = call_llm(
        system_prompt=system_prompt,
        user_message=user_message,
        response_schema=CaptionX,
        model=AGENT_CAPTION_X_MODEL,
    )

    logger.info(f"Agent Caption X: caption dibuat untuk '{result.news_ref_title}'")
    return result
