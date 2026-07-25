"""
agents/agent_image_generation.py
Node 4 — Agent Image Generation.
Buat prompt image generation dari caption IG, lalu generate gambar.
"""

import json
import logging

from tools.llm_client import call_llm
from config.schemas import CaptionIG, ImageGenResult
from config.settings import load_prompt, AGENT_IMAGE_GEN_MODEL
from tools.image_gen_client import generate_image

logger = logging.getLogger(__name__)


def run(caption_ig: CaptionIG, run_id: str = "") -> ImageGenResult:
    """
    Jalankan Agent Image Generation — buat gambar untuk posting IG.

    Flow:
    1. LLM membuat prompt image generation berdasarkan caption IG
    2. Prompt dikirim ke image generation API
    3. Gambar disimpan ke data/images/

    Args:
        caption_ig: CaptionIG dari Agent Caption IG.
        run_id: ID run pipeline (untuk penamaan file).

    Returns:
        ImageGenResult berisi prompt, dan path gambar yang dihasilkan.
    """
    logger.info(
        f"Agent Image Gen: membuat gambar untuk '{caption_ig.news_ref_title}'"
    )

    # Step 1: LLM membuat image prompt
    system_prompt = load_prompt("image_prompt.md")

    user_message = (
        f"Buatkan prompt image generation untuk berita berikut:\n\n"
        f"Judul: {caption_ig.news_ref_title}\n"
        f"Caption IG: {caption_ig.caption_short}\n\n"
        f"Buat prompt yang akan menghasilkan gambar eye-catching untuk Instagram post."
    )

    # Minta LLM hasilkan ImageGenResult (dengan image_prompt terisi, image_path kosong)
    llm_result = call_llm(
        system_prompt=system_prompt,
        user_message=user_message,
        response_schema=ImageGenResult,
        model=AGENT_IMAGE_GEN_MODEL,
        agent_name="image_gen",
    )

    logger.info(f"Agent Image Gen: image prompt = '{llm_result.image_prompt[:100]}...'")

    # Step 2: Generate gambar dari prompt
    try:
        image_path = generate_image(
            prompt=llm_result.image_prompt,
            run_id=run_id,
        )
        logger.info(f"Agent Image Gen: gambar disimpan di {image_path}")
    except Exception as e:
        logger.error(f"Agent Image Gen: gagal generate gambar: {e}")
        raise

    # Step 3: Return hasil lengkap
    return ImageGenResult(
        news_ref_title=llm_result.news_ref_title,
        image_prompt=llm_result.image_prompt,
        image_path=image_path,
    )
