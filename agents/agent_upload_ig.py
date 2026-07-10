"""
agents/agent_upload_ig.py
Node 6b — Agent Upload IG.
Post caption + gambar ke Instagram.
"""

import logging

from config.schemas import CaptionIG, ImageGenResult, UploadResult
from tools.ig_api_client import post_image, upload_image_to_hosting

logger = logging.getLogger(__name__)


def run(caption_ig: CaptionIG, image_result: ImageGenResult) -> UploadResult:
    """
    Jalankan Agent Upload IG — posting caption + gambar ke Instagram.

    Flow:
    1. Upload gambar lokal ke hosting publik (IG butuh URL publik)
    2. Post ke Instagram via Graph API

    Args:
        caption_ig: CaptionIG yang sudah di-approve user.
        image_result: ImageGenResult dengan path gambar lokal.

    Returns:
        UploadResult dengan status posting.
    """
    logger.info(f"Agent Upload IG: posting '{caption_ig.news_ref_title}'")

    try:
        # Step 1: Upload gambar ke hosting publik
        logger.info(f"Agent Upload IG: uploading image dari {image_result.image_path}")
        image_url = upload_image_to_hosting(image_result.image_path)

        # Step 2: Post ke Instagram
        logger.info(f"Agent Upload IG: posting ke Instagram...")
        result = post_image(
            image_url=image_url,
            caption=caption_ig.caption_short,
        )

        logger.info(f"Agent Upload IG: sukses posting di {result.get('post_url')}")

        return UploadResult(
            platform="instagram",
            success=True,
            post_url=result.get("post_url"),
        )

    except Exception as e:
        logger.error(f"Agent Upload IG: gagal posting: {e}")
        return UploadResult(
            platform="instagram",
            success=False,
            error=str(e),
        )
