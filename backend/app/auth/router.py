from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Response
import redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.db.database import get_db
from app.db.models import User
from app.auth.jwt_handler import create_access_token, decode_access_token, revoke_token
from app.auth.oauth import (
    get_google_auth_url,
    exchange_code_for_tokens,
    get_google_user_info,
    generate_csrf_state,
    store_csrf_state,
    verify_csrf_state,
)
from app.config import get_settings
from app.security.encryption import encrypt_drive_token

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


def set_access_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        "access_token",
        token,
        httponly=True,
        secure=settings.app_env == "production",
        samesite="lax",
        max_age=settings.jwt_access_token_expire_minutes * 60,
    )


@router.get("/login/google")
async def login_google(role: str = Query("attendee", enum=["attendee", "organizer"])):
    """Redirect to Google consent screen"""
    state = generate_csrf_state()
    store_csrf_state(state, role=role)

    url = get_google_auth_url(state, role=role)
    return {"redirect_url": url}


@router.get("/callback")
async def auth_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Handle Google OAuth callback"""
    # Verify CSRF state
    role = verify_csrf_state(state)
    if not role:
        raise HTTPException(status_code=400, detail="Invalid CSRF state")

    # Exchange code for tokens
    try:
        tokens = await exchange_code_for_tokens(code, settings.google_redirect_uri)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {str(e)}")

    # Get user info
    user_info = await get_google_user_info(tokens["access_token"])

    # Upsert user
    stmt = select(User).where(User.google_sub == user_info["sub"])
    result = await db.execute(stmt)
    user = result.scalars().first()

    if not user:
        user = User(
            google_sub=user_info["sub"],
            email=user_info["email"],
            name=user_info.get("name"),
        )
        db.add(user)
        await db.flush()
    else:
        user.last_login = datetime.utcnow()

    await db.commit()
    await db.refresh(user)

    if role == "organizer" and tokens.get("refresh_token"):
        r = redis.from_url(settings.redis_url)
        encrypted_refresh = encrypt_drive_token(
            tokens["refresh_token"],
            settings.master_encryption_key.encode("utf-8"),
        )
        r.set(f"drive_refresh_token:{user.user_id}", encrypted_refresh)

    # Create JWT
    access_token = create_access_token(
        user_id=str(user.user_id),
        event_id="",
        scope=role,
    )

    response = Response()
    set_access_cookie(response, access_token)
    response.status_code = 302
    response.headers["Location"] = "http://localhost:5173/"
    return response


@router.post("/refresh")
async def refresh_token(
    response: Response,
    access_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Refresh access token"""
    if not access_token:
        raise HTTPException(status_code=401, detail="No token provided")

    try:
        payload = decode_access_token(access_token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.user_id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")

    new_token = create_access_token(
        user_id=str(user.user_id),
        event_id=payload.get("event_id", ""),
        scope=payload.get("scope", "attendee"),
    )
    set_access_cookie(response, new_token)
    return {"status": "ok"}


@router.post("/dev-login")
async def dev_login(
    response: Response,
    role: str = Query("attendee", enum=["attendee", "organizer"]),
    db: AsyncSession = Depends(get_db),
):
    """Create a local development session without Google OAuth."""
    if settings.app_env == "production":
        raise HTTPException(status_code=404, detail="Not found")

    google_sub = f"dev-{role}"
    result = await db.execute(select(User).where(User.google_sub == google_sub))
    user = result.scalars().first()
    if not user:
        user = User(
            google_sub=google_sub,
            email=f"{role}@facefind.local",
            name=f"Dev {role.title()}",
            consent_given=role == "organizer",
            consent_at=datetime.utcnow() if role == "organizer" else None,
        )
        db.add(user)
        await db.flush()
    user.last_login = datetime.utcnow()
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user_id=str(user.user_id), event_id="", scope=role)
    set_access_cookie(response, token)
    return {
        "user": {
            "name": user.name,
            "email": user.email,
            "scope": role,
            "consentGiven": user.consent_given,
        }
    }


@router.post("/logout")
async def logout(access_token: str | None = Cookie(default=None)):
    """Logout user. Revokes the token server-side (not just clearing the
    cookie) so a copy captured before logout - via a leaked cookie, shared
    device, or intercepted request - stops working immediately instead of
    remaining valid for the rest of its lifetime."""
    if access_token:
        try:
            payload = decode_access_token(access_token)
            jti = payload.get("jti")
            exp = payload.get("exp")
            if jti and exp:
                remaining = int(exp - datetime.utcnow().timestamp())
                if remaining > 0:
                    revoke_token(jti, remaining)
        except ValueError:
            pass

    response = Response()
    response.delete_cookie("access_token")
    response.status_code = 200
    return {"message": "Logged out"}
