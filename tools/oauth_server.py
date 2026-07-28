"""
tools/oauth_server.py
Mini Flask server untuk handle OAuth callback dari X dan Instagram.
Server berjalan sementara di localhost — hanya aktif saat proses login.
"""

import logging
import secrets
import threading
import time
import webbrowser
from urllib.parse import urlencode

from flask import Flask, request, redirect

logger = logging.getLogger(__name__)

# ── Shared state untuk OAuth flow ────────────────────────────────────────────
_oauth_state: dict = {}
_oauth_result: dict = {}
_pkce_store: dict = {}
_server_thread: threading.Thread | None = None
_shutdown_event = threading.Event()


def _get_shared_state() -> tuple[dict, dict, dict]:
    """
    Return (oauth_state, oauth_result, pkce_store) dicts.
    Di production (Render), return dict dari backend.app agar sinkron
    dengan callback routes. Di lokal, return local dicts.
    """
    import os as _os
    if _os.environ.get("RENDER"):
        try:
            from backend.app import (
                _oauth_state as prod_state,
                _oauth_result as prod_result,
                _pkce_store as prod_pkce,
            )
            return prod_state, prod_result, prod_pkce
        except ImportError:
            pass
    return _oauth_state, _oauth_result, _pkce_store


def _create_app() -> Flask:
    """Buat Flask app untuk OAuth callback."""
    app = Flask(__name__)
    app.logger.setLevel(logging.WARNING)  # Suppress Flask logs

    @app.route("/callback/x")
    def callback_x():
        """Handle OAuth callback dari X/Twitter."""
        code = request.args.get("code")
        state = request.args.get("state")
        error = request.args.get("error")

        if error:
            _oauth_result["x"] = {"error": error}
            return _success_page("X/Twitter", success=False, error=error)

        if state != _oauth_state.get("x"):
            _oauth_result["x"] = {"error": "State mismatch — kemungkinan CSRF attack."}
            return _success_page("X/Twitter", success=False, error="State mismatch")

        _oauth_result["x"] = {"code": code}
        return _success_page("X/Twitter", success=True)

    @app.route("/callback/ig")
    def callback_ig():
        """Handle OAuth callback dari Instagram/Facebook."""
        code = request.args.get("code")
        error = request.args.get("error")
        error_reason = request.args.get("error_reason", "")

        if error:
            _oauth_result["ig"] = {"error": f"{error}: {error_reason}"}
            return _success_page("Instagram", success=False, error=error_reason)

        _oauth_result["ig"] = {"code": code}
        return _success_page("Instagram", success=True)

    @app.route("/health")
    def health():
        return "OK", 200

    return app


def _success_page(platform: str, success: bool, error: str = "") -> str:
    """HTML response page setelah OAuth callback."""
    if success:
        return f"""
        <html>
        <body style="font-family: sans-serif; text-align: center; padding: 60px;
                     background: #1a1a2e; color: #fff;">
            <h1 style="color: #4CAF50;">✅ Login {platform} Berhasil!</h1>
            <p>Akun {platform} berhasil terkoneksi dengan Glitch Media.</p>
            <p style="color: #888;">Tab ini bisa ditutup. Kembali ke notebook.</p>
        </body>
        </html>
        """
    else:
        return f"""
        <html>
        <body style="font-family: sans-serif; text-align: center; padding: 60px;
                     background: #1a1a2e; color: #fff;">
            <h1 style="color: #f44336;">❌ Login {platform} Gagal</h1>
            <p>Error: {error}</p>
            <p style="color: #888;">Coba lagi dari notebook.</p>
        </body>
        </html>
        """


def start_server(port: int) -> None:
    """Start OAuth callback server di background thread."""
    global _server_thread, _shutdown_event

    _shutdown_event.clear()
    _oauth_result.clear()

    app = _create_app()

    def run():
        from werkzeug.serving import make_server
        server = make_server("127.0.0.1", port, app)
        server.timeout = 1
        logger.info(f"OAuth server started on http://localhost:{port}")
        while not _shutdown_event.is_set():
            server.handle_request()
        server.server_close()
        logger.info("OAuth server stopped.")

    _server_thread = threading.Thread(target=run, daemon=True)
    _server_thread.start()
    time.sleep(0.5)  # Tunggu server siap


def stop_server() -> None:
    """Stop OAuth callback server."""
    global _server_thread
    _shutdown_event.set()
    if _server_thread:
        _server_thread.join(timeout=3)
        _server_thread = None


def wait_for_callback(platform: str, timeout: int = 120) -> dict:
    """
    Tunggu OAuth callback dari browser.

    Args:
        platform: 'x' atau 'ig'.
        timeout: Timeout dalam detik.

    Returns:
        Dict dengan 'code' atau 'error'.
    """
    _, result_store, _ = _get_shared_state()

    start = time.time()
    while time.time() - start < timeout:
        if platform in result_store:
            return result_store[platform]
        time.sleep(0.5)
    return {"error": f"Timeout — tidak ada response dari {platform} dalam {timeout} detik."}


def generate_state(platform: str) -> str:
    """Generate dan simpan CSRF state token."""
    state = secrets.token_urlsafe(32)
    state_store, _, _ = _get_shared_state()
    state_store[platform] = state
    return state


# ── X/Twitter OAuth 2.0 PKCE ────────────────────────────────────────────────



def initiate_x_login() -> dict:
    """
    Mulai OAuth 2.0 PKCE flow untuk X/Twitter — return auth URL.
    Dipakai oleh web UI agar frontend bisa membuka URL di tab baru.

    Returns:
        Dict dengan 'auth_url' atau 'error'.
    """
    import hashlib
    import base64
    from config.settings import (
        X_OAUTH_CLIENT_ID,
        X_OAUTH_REDIRECT_URI,
        OAUTH_SERVER_PORT,
    )

    if not X_OAUTH_CLIENT_ID:
        return {"error": "X_OAUTH_CLIENT_ID belum diset di .env"}

    # Generate PKCE code verifier & challenge
    code_verifier = secrets.token_urlsafe(64)[:128]
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b"=").decode()

    state = generate_state("x")

    # Simpan code_verifier untuk dipakai saat exchange
    _, _, pkce_store = _get_shared_state()
    pkce_store["x_code_verifier"] = code_verifier

    # Build authorization URL
    auth_params = {
        "response_type": "code",
        "client_id": X_OAUTH_CLIENT_ID,
        "redirect_uri": X_OAUTH_REDIRECT_URI,
        "scope": "tweet.read tweet.write users.read offline.access",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    auth_url = f"https://twitter.com/i/oauth2/authorize?{urlencode(auth_params)}"

    # Start callback server only if not running in production (Render)
    import os
    if not os.environ.get("RENDER"):
        start_server(OAUTH_SERVER_PORT)

    logger.info(f"X OAuth initiated, auth_url ready")
    return {"auth_url": auth_url}


def complete_x_login(timeout: int = 120) -> dict:
    """
    Tunggu OAuth callback dari X, exchange code, simpan token.
    Harus dipanggil setelah initiate_x_login().

    Args:
        timeout: Timeout dalam detik.

    Returns:
        Dict dengan 'success', 'username', 'display_name' atau 'error'.
    """
    import requests
    from config.settings import (
        X_OAUTH_CLIENT_ID,
        X_OAUTH_CLIENT_SECRET,
        X_OAUTH_REDIRECT_URI,
    )
    from tools.oauth_manager import save_tokens

    try:
        # Tunggu callback
        logger.info("Waiting for X OAuth callback...")
        result = wait_for_callback("x", timeout=timeout)

        if "error" in result:
            return {"error": result["error"]}

        code = result["code"]
        _, _, pkce_store = _get_shared_state()
        code_verifier = pkce_store.get("x_code_verifier", "")

        # Exchange code for token
        logger.info("Exchanging X authorization code for access token...")
        token_response = requests.post(
            "https://api.twitter.com/2/oauth2/token",
            data={
                "code": code,
                "grant_type": "authorization_code",
                "client_id": X_OAUTH_CLIENT_ID,
                "redirect_uri": X_OAUTH_REDIRECT_URI,
                "code_verifier": code_verifier,
            },
            auth=(X_OAUTH_CLIENT_ID, X_OAUTH_CLIENT_SECRET) if X_OAUTH_CLIENT_SECRET else None,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        token_response.raise_for_status()
        token_data = token_response.json()

        access_token = token_data["access_token"]
        refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in", 7200)

        # Ambil info user
        user_response = requests.get(
            "https://api.twitter.com/2/users/me",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15,
        )
        user_response.raise_for_status()
        user_data = user_response.json().get("data", {})

        # Simpan token
        save_tokens("x", {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": time.time() + expires_in,
            "token_type": "bearer",
            "scope": token_data.get("scope", ""),
            "account_info": {
                "user_id": user_data.get("id"),
                "username": user_data.get("username"),
                "display_name": user_data.get("name"),
            },
        })

        username = user_data.get("username", "Unknown")
        logger.info(f"X OAuth complete — connected as @{username}")
        return {
            "success": True,
            "username": username,
            "display_name": user_data.get("name"),
        }

    except Exception as e:
        logger.error(f"X OAuth complete error: {e}")
        return {"error": str(e)}
    finally:
        stop_server()


def login_x() -> dict:
    """
    Jalankan OAuth 2.0 PKCE flow untuk X/Twitter (backward compatible).
    Buka browser → user login → callback → exchange code → simpan token.

    Returns:
        Dict dengan status login.
    """
    initiation = initiate_x_login()
    if "error" in initiation:
        return initiation

    auth_url = initiation["auth_url"]
    print(f"🌐 Membuka browser untuk login X/Twitter...")
    print(f"   URL: {auth_url}")
    webbrowser.open(auth_url)

    print("⏳ Menunggu login di browser...")
    return complete_x_login(timeout=120)


# ── Instagram OAuth (Facebook Login) ────────────────────────────────────────

def initiate_ig_login() -> dict:
    """
    Mulai OAuth flow untuk Instagram — return auth URL.
    Dipakai oleh web UI agar frontend bisa membuka URL di tab baru.

    Returns:
        Dict dengan 'auth_url' atau 'error'.
    """
    from config.settings import (
        IG_OAUTH_APP_ID,
        IG_OAUTH_APP_SECRET,
        IG_OAUTH_REDIRECT_URI,
        OAUTH_SERVER_PORT,
    )

    if not IG_OAUTH_APP_ID:
        return {"error": "IG_OAUTH_APP_ID belum diset di .env"}
    if not IG_OAUTH_APP_SECRET:
        return {"error": "IG_OAUTH_APP_SECRET belum diset di .env"}

    state = generate_state("ig")

    # Build Facebook OAuth URL
    auth_params = {
        "client_id": IG_OAUTH_APP_ID,
        "redirect_uri": IG_OAUTH_REDIRECT_URI,
        "scope": "instagram_basic,instagram_content_publish,pages_show_list,pages_read_engagement",
        "response_type": "code",
        "state": state,
    }
    auth_url = f"https://www.facebook.com/v18.0/dialog/oauth?{urlencode(auth_params)}"

    # Start callback server only if not running in production (Render)
    import os
    if not os.environ.get("RENDER"):
        start_server(OAUTH_SERVER_PORT)

    logger.info(f"IG OAuth initiated, auth_url ready")
    return {"auth_url": auth_url}


def complete_ig_login(timeout: int = 120) -> dict:
    """
    Tunggu OAuth callback dari IG, exchange code, simpan token.
    Harus dipanggil setelah initiate_ig_login().

    Args:
        timeout: Timeout dalam detik.

    Returns:
        Dict dengan 'success', 'username', 'display_name', 'account_id' atau 'error'.
    """
    import requests
    from config.settings import (
        IG_OAUTH_APP_ID,
        IG_OAUTH_APP_SECRET,
        IG_OAUTH_REDIRECT_URI,
    )
    from tools.oauth_manager import save_tokens

    try:
        logger.info("Waiting for IG OAuth callback...")
        result = wait_for_callback("ig", timeout=timeout)

        if "error" in result:
            return {"error": result["error"]}

        code = result["code"]

        # Exchange code for short-lived token
        logger.info("Exchanging IG authorization code for access token...")
        token_response = requests.get(
            "https://graph.facebook.com/v18.0/oauth/access_token",
            params={
                "client_id": IG_OAUTH_APP_ID,
                "client_secret": IG_OAUTH_APP_SECRET,
                "redirect_uri": IG_OAUTH_REDIRECT_URI,
                "code": code,
            },
            timeout=30,
        )
        token_response.raise_for_status()
        token_data = token_response.json()
        short_token = token_data["access_token"]

        # Exchange for long-lived token (60 hari)
        logger.info("Exchanging to long-lived token...")
        long_response = requests.get(
            "https://graph.facebook.com/v18.0/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": IG_OAUTH_APP_ID,
                "client_secret": IG_OAUTH_APP_SECRET,
                "fb_exchange_token": short_token,
            },
            timeout=30,
        )
        long_response.raise_for_status()
        long_data = long_response.json()
        long_token = long_data["access_token"]
        expires_in = long_data.get("expires_in", 5184000)  # default 60 hari

        # Ambil Facebook Pages yang dimiliki user
        logger.info("Searching for connected Instagram Business account...")
        pages_response = requests.get(
            "https://graph.facebook.com/v18.0/me/accounts",
            params={"access_token": long_token},
            timeout=15,
        )
        pages_response.raise_for_status()
        pages = pages_response.json().get("data", [])

        if not pages:
            return {"error": "Tidak ada Facebook Page yang ditemukan. Instagram Business membutuhkan Facebook Page."}

        # Cari Instagram Business Account dari setiap Page
        ig_account = None
        page_token = None
        for page in pages:
            ig_response = requests.get(
                f"https://graph.facebook.com/v18.0/{page['id']}",
                params={
                    "fields": "instagram_business_account,name",
                    "access_token": long_token,
                },
                timeout=15,
            )
            ig_response.raise_for_status()
            ig_data = ig_response.json()

            if "instagram_business_account" in ig_data:
                ig_account = ig_data["instagram_business_account"]
                page_token = page.get("access_token", long_token)
                break

        if not ig_account:
            return {
                "error": "Tidak ada Instagram Business Account yang terkoneksi ke Facebook Page. "
                         "Pastikan akun IG sudah diubah ke Business/Creator dan terhubung ke Facebook Page."
            }

        ig_account_id = ig_account["id"]

        # Ambil info IG account
        ig_info_response = requests.get(
            f"https://graph.facebook.com/v18.0/{ig_account_id}",
            params={
                "fields": "username,name,profile_picture_url",
                "access_token": page_token,
            },
            timeout=15,
        )
        ig_info_response.raise_for_status()
        ig_info = ig_info_response.json()

        # Simpan token
        save_tokens("ig", {
            "access_token": page_token,
            "long_lived_token": long_token,
            "expires_at": time.time() + expires_in,
            "ig_business_account_id": ig_account_id,
            "account_info": {
                "username": ig_info.get("username"),
                "display_name": ig_info.get("name"),
                "profile_picture": ig_info.get("profile_picture_url"),
                "account_id": ig_account_id,
            },
        })

        username = ig_info.get("username", "Unknown")
        logger.info(f"IG OAuth complete — connected as @{username}")
        return {
            "success": True,
            "username": username,
            "display_name": ig_info.get("name"),
            "account_id": ig_account_id,
        }

    except Exception as e:
        logger.error(f"IG OAuth complete error: {e}")
        return {"error": str(e)}
    finally:
        stop_server()


def login_ig() -> dict:
    """
    Jalankan OAuth flow untuk Instagram (backward compatible).
    Buka browser → user login → callback → exchange code → get IG account → simpan token.

    Returns:
        Dict dengan status login.
    """
    initiation = initiate_ig_login()
    if "error" in initiation:
        return initiation

    auth_url = initiation["auth_url"]
    print(f"🌐 Membuka browser untuk login Instagram...")
    print(f"   URL: {auth_url}")
    webbrowser.open(auth_url)

    print("⏳ Menunggu login di browser...")
    return complete_ig_login(timeout=120)
