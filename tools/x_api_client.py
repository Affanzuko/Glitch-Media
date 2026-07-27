"""
tools/x_api_client.py
Wrapper posting ke X (Twitter API v2) — menggunakan tweepy.
Mendukung 2 mode autentikasi:
  1. OAuth 2.0 User Token (dari login via browser) — prioritas utama
  2. OAuth 1.0a static keys (dari .env) — fallback
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
_client_mode = None  # 'oauth2_user' atau 'oauth1'


def _get_client():
    """
    Lazy-init Tweepy Client.
    Prioritas: OAuth 2.0 user token (dari login) > OAuth 1.0a static keys (.env).
    
    Untuk OAuth 2.0 PKCE user token, kita return dict mode info.
    Tweepy Client hanya dipakai untuk OAuth 1.0a.
    """
    import tweepy
    from tools.oauth_manager import get_access_token

    global _client, _client_mode

    # Cek apakah ada OAuth 2.0 user token
    oauth2_token = get_access_token("x")

    if oauth2_token:
        # OAuth 2.0 User Context — simpan token saja, 
        # posting via direct API call (bukan Tweepy Client)
        if _client is None or _client_mode != "oauth2_user":
            _client = {"oauth2_token": oauth2_token}
            _client_mode = "oauth2_user"
            logger.info("X client initialized with OAuth 2.0 user token (direct API)")
        return _client

    # Fallback ke OAuth 1.0a static keys
    if _client is None or _client_mode != "oauth1":
        if not TWITTER_API_KEY:
            raise RuntimeError(
                "Tidak ada kredensial X/Twitter. "
                "Login via OAuth (tools.oauth_server.login_x()) atau set API keys di .env"
            )
        _client = tweepy.Client(
            bearer_token=TWITTER_BEARER_TOKEN or None,
            consumer_key=TWITTER_API_KEY,
            consumer_secret=TWITTER_API_SECRET,
            access_token=TWITTER_ACCESS_TOKEN,
            access_token_secret=TWITTER_ACCESS_SECRET,
        )
        _client_mode = "oauth1"
        logger.info("X client initialized with OAuth 1.0a static keys")
    return _client


def reset_client():
    """Reset client agar di-reinitialize pada panggilan berikutnya."""
    global _client, _client_mode
    _client = None
    _client_mode = None


def _post_tweet_oauth2(token: str, text: str, reply_to: str | None = None) -> dict:
    """Post tweet via Twitter API v2 menggunakan OAuth 2.0 User Context (direct HTTP)."""
    import requests as http_requests

    url = "https://api.twitter.com/2/tweets"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {"text": text}
    if reply_to:
        payload["reply"] = {"in_reply_to_tweet_id": reply_to}

    resp = http_requests.post(url, json=payload, headers=headers, timeout=30)

    if resp.status_code == 429:
        raise Exception(f"Rate limited (429). Retry-After: {resp.headers.get('Retry-After', 'unknown')}")

    if resp.status_code not in (200, 201):
        error_detail = resp.text
        try:
            error_json = resp.json()
            error_detail = error_json.get("detail", error_json.get("title", resp.text))
        except Exception:
            pass
        raise Exception(f"{resp.status_code} {error_detail}")

    data = resp.json().get("data", {})
    tweet_id = data.get("id")
    return {"tweet_id": tweet_id, "post_url": f"https://twitter.com/i/status/{tweet_id}"}


def _post_tweet_tweepy(client, text: str, reply_to: str | None = None) -> dict:
    """Post tweet via Tweepy Client (OAuth 1.0a)."""
    kwargs = {"text": text}
    if reply_to:
        kwargs["in_reply_to_tweet_id"] = reply_to

    response = client.create_tweet(**kwargs)
    tweet_id = response.data["id"]
    return {"tweet_id": tweet_id, "post_url": f"https://twitter.com/i/status/{tweet_id}"}


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
    is_oauth2 = isinstance(client, dict)

    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(f"X posting attempt {attempt}/{MAX_RETRIES}")

            if is_oauth2:
                result = _post_tweet_oauth2(client["oauth2_token"], text)
            else:
                result = _post_tweet_tweepy(client, text)

            logger.info(f"Tweet posted successfully: {result['post_url']}")
            return {
                "success": True,
                "post_url": result["post_url"],
                "tweet_id": result["tweet_id"],
            }

        except Exception as e:
            last_error = e
            delay = min(RETRY_BASE_DELAY * (2 ** (attempt - 1)), RETRY_MAX_DELAY)
            logger.warning(f"X API error on attempt {attempt}: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(delay)

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
    is_oauth2 = isinstance(client, dict)

    tweet_ids: list[str] = []
    reply_to: str | None = None

    for i, text in enumerate(tweets):
        last_error: Exception | None = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                if is_oauth2:
                    result = _post_tweet_oauth2(client["oauth2_token"], text, reply_to=reply_to)
                else:
                    result = _post_tweet_tweepy(client, text, reply_to=reply_to)

                tweet_id = result["tweet_id"]
                tweet_ids.append(tweet_id)
                reply_to = tweet_id

                logger.info(f"Thread tweet {i+1}/{len(tweets)} posted: {tweet_id}")
                break

            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    delay = min(RETRY_BASE_DELAY * (2 ** (attempt - 1)), RETRY_MAX_DELAY)
                    logger.warning(f"X error on tweet {i+1}, attempt {attempt}, retry in {delay}s: {e}")
                    time.sleep(delay)
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

