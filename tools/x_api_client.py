"""
tools/x_api_client.py
Wrapper posting ke X (Twitter API v2) — menggunakan tweepy.
Retry + exponential backoff + step/attempt budget.
"""

import logging
import time

from config.settings import (
    TWITTER_API_KEY,
    TWITTER_API_SECRET,
    TWITTER_ACCESS_TOKEN,
    TWITTER_ACCESS_SECRET,
    TWITTER_BEARER_TOKEN,
    MAX_RETRIES,
    RETRY_BASE_DELAY,
    RETRY_MAX_DELAY,
)

logger = logging.getLogger(__name__)

# Singleton client instance
_client = None


def _get_client():
    """Lazy-init Tweepy Client dengan OAuth 1.0a (untuk posting)."""
    import tweepy

    global _client
    if _client is None:
        _client = tweepy.Client(
            bearer_token=TWITTER_BEARER_TOKEN,
            consumer_key=TWITTER_API_KEY,
            consumer_secret=TWITTER_API_SECRET,
            access_token=TWITTER_ACCESS_TOKEN,
            access_token_secret=TWITTER_ACCESS_SECRET,
        )
    return _client


def post_tweet(text: str) -> dict:
    """
    Post tweet ke X/Twitter.

    Args:
        text: Teks tweet (max 280 karakter per tweet).

    Returns:
        Dict dengan 'success', 'post_url', dan 'tweet_id'.

    Raises:
        RuntimeError: Jika semua retry gagal.
    """
    client = _get_client()
    import tweepy

    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(f"X posting attempt {attempt}/{MAX_RETRIES}")

            response = client.create_tweet(text=text)

            tweet_id = response.data["id"]
            # Ambil username dari auth user (opsional, bisa di-hardcode)
            post_url = f"https://twitter.com/i/status/{tweet_id}"

            logger.info(f"Tweet posted successfully: {post_url}")
            return {
                "success": True,
                "post_url": post_url,
                "tweet_id": tweet_id,
            }

        except tweepy.TooManyRequests as e:
            last_error = e
            delay = min(RETRY_BASE_DELAY * (2 ** (attempt - 1)), RETRY_MAX_DELAY)
            logger.warning(f"X rate limited, retry in {delay}s")
            time.sleep(delay)

        except tweepy.TweepyException as e:
            last_error = e
            delay = min(RETRY_BASE_DELAY * (2 ** (attempt - 1)), RETRY_MAX_DELAY)
            logger.warning(f"X API error, retry in {delay}s: {e}")
            time.sleep(delay)

        except Exception as e:
            last_error = e
            logger.error(f"X unexpected error on attempt {attempt}: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BASE_DELAY)

    raise RuntimeError(
        f"X posting gagal setelah {MAX_RETRIES} attempts. Last error: {last_error}"
    )


def post_thread(tweets: list[str]) -> dict:
    """
    Post thread (multiple tweets berurutan) ke X/Twitter.

    Args:
        tweets: List of tweet texts (masing-masing max 280 char).

    Returns:
        Dict dengan 'success', 'post_url' (URL tweet pertama), dan 'tweet_ids'.
    """
    client = _get_client()
    import tweepy

    tweet_ids: list[str] = []
    reply_to: str | None = None

    for i, text in enumerate(tweets):
        last_error: Exception | None = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                kwargs = {"text": text}
                if reply_to:
                    kwargs["in_reply_to_tweet_id"] = reply_to

                response = client.create_tweet(**kwargs)
                tweet_id = response.data["id"]
                tweet_ids.append(tweet_id)
                reply_to = tweet_id

                logger.info(f"Thread tweet {i+1}/{len(tweets)} posted: {tweet_id}")
                break

            except tweepy.TooManyRequests as e:
                last_error = e
                delay = min(RETRY_BASE_DELAY * (2 ** (attempt - 1)), RETRY_MAX_DELAY)
                logger.warning(f"X rate limited on tweet {i+1}, retry in {delay}s")
                time.sleep(delay)

            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_BASE_DELAY)
        else:
            raise RuntimeError(
                f"X thread posting gagal pada tweet {i+1}. Last error: {last_error}"
            )

    first_url = f"https://twitter.com/i/status/{tweet_ids[0]}" if tweet_ids else None
    return {
        "success": True,
        "post_url": first_url,
        "tweet_ids": tweet_ids,
    }
