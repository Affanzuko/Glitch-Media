"""
agents/agent_upload_x.py
Node 6a — Agent Upload X.
Post caption ke X/Twitter.
"""

import logging

from config.schemas import CaptionX, UploadResult
from tools.x_api_client import post_tweet, post_thread

logger = logging.getLogger(__name__)

# Batas karakter per tweet
TWEET_MAX_LENGTH = 280


def run(caption_x: CaptionX) -> UploadResult:
    """
    Jalankan Agent Upload X — posting caption ke X/Twitter.

    Jika caption melebihi 280 karakter, dipecah menjadi thread.

    Args:
        caption_x: CaptionX yang sudah di-approve user.

    Returns:
        UploadResult dengan status posting.
    """
    logger.info(f"Agent Upload X: posting '{caption_x.news_ref_title}'")

    try:
        caption = caption_x.caption_long

        # Cek apakah perlu thread (caption > 280 char atau ada delimiter ---)
        if "---" in caption:
            # Split by thread delimiter
            tweets = [t.strip() for t in caption.split("---") if t.strip()]
            result = post_thread(tweets)
        elif len(caption) > TWEET_MAX_LENGTH:
            # Auto-split jadi thread berdasarkan kalimat
            tweets = _split_into_tweets(caption)
            result = post_thread(tweets)
        else:
            # Single tweet
            result = post_tweet(caption)

        logger.info(f"Agent Upload X: sukses posting di {result.get('post_url')}")

        return UploadResult(
            platform="x",
            success=True,
            post_url=result.get("post_url"),
        )

    except Exception as e:
        logger.error(f"Agent Upload X: gagal posting: {e}")
        return UploadResult(
            platform="x",
            success=False,
            error=str(e),
        )


def _split_into_tweets(text: str, max_length: int = TWEET_MAX_LENGTH) -> list[str]:
    """
    Pecah teks panjang menjadi beberapa tweet berdasarkan kalimat.
    Setiap tweet tidak melebihi max_length karakter.
    """
    sentences = text.replace(". ", ".\n").split("\n")
    tweets: list[str] = []
    current_tweet = ""

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        # Jika menambahkan kalimat masih dalam batas
        test_tweet = f"{current_tweet} {sentence}".strip() if current_tweet else sentence

        if len(test_tweet) <= max_length:
            current_tweet = test_tweet
        else:
            # Simpan tweet saat ini, mulai tweet baru
            if current_tweet:
                tweets.append(current_tweet)
            current_tweet = sentence

            # Jika satu kalimat saja sudah > max_length, potong paksa
            if len(current_tweet) > max_length:
                while len(current_tweet) > max_length:
                    tweets.append(current_tweet[:max_length])
                    current_tweet = current_tweet[max_length:]

    if current_tweet:
        tweets.append(current_tweet)

    # Tambahkan nomor thread jika lebih dari 1 tweet
    if len(tweets) > 1:
        tweets = [f"{t} ({i+1}/{len(tweets)})" for i, t in enumerate(tweets)]

    return tweets
