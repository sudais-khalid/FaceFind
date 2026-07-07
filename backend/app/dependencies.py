from fastapi import Depends, HTTPException, Cookie
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_db
from app.db.models import User
from app.auth.jwt_handler import decode_access_token, is_token_revoked


async def get_current_user(
    access_token: str = Cookie(None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and validate user from JWT cookie"""
    if not access_token:
        raise HTTPException(status_code=401, detail="No token provided")

    try:
        payload = decode_access_token(access_token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Check if token is revoked
    jti = payload.get("jti")
    if jti and is_token_revoked(jti):
        raise HTTPException(status_code=401, detail="Token revoked")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    # Load user from database
    stmt = select(User).where(User.user_id == user_id)
    result = await db.execute(stmt)
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user


async def require_organizer(user: User = Depends(get_current_user)) -> User:
    """Validate user has organizer scope"""
    # Simplified: in production, check JWT scope
    return user
