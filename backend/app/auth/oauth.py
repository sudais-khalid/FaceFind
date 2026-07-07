import httpx
import secrets
import redis
from urllib.parse import urlencode

from app.config import get_settings

settings = get_settings()


def get_google_auth_url(state: str, role: str = "attendee") -> str:
    """Generate Google OAuth authorization URL"""
    scopes = ["openid", "email", "profile"]
    if role == "organizer":
        scopes.append("https://www.googleapis.com/auth/drive.readonly")

    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": " ".join(scopes),
        "state": state,
        "access_type": "offline",
        "prompt": "consent" if role == "organizer" else "select_account",
    }

    query_string = urlencode(params)
    return f"https://accounts.google.com/o/oauth2/v2/auth?{query_string}"


async def exchange_code_for_tokens(code: str, redirect_uri: str) -> dict:
    """Exchange authorization code for tokens"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
        )
        response.raise_for_status()
        return response.json()


async def get_google_user_info(access_token: str) -> dict:
    """Get user profile from Google"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        return response.json()


async def refresh_google_token(refresh_token: str) -> dict:
    """Refresh Google access token"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        response.raise_for_status()
        return response.json()


def generate_csrf_state() -> str:
    """Generate random CSRF state token"""
    return secrets.token_urlsafe(32)


def store_csrf_state(state: str, role: str = "attendee") -> None:
    """Store CSRF state in Redis for 5 minutes"""
    r = redis.from_url(settings.redis_url)
    r.setex(f"oauth_state:{state}", 300, role)


def verify_csrf_state(state: str) -> str | None:
    """Verify and consume CSRF state"""
    r = redis.from_url(settings.redis_url)
    key = f"oauth_state:{state}"
    role = r.get(key)
    if not role:
        return None
    r.delete(key)
    return role.decode("utf-8") if isinstance(role, bytes) else str(role)
