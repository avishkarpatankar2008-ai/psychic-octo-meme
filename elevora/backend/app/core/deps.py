from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import Cookie, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import get_settings
from app.core.security import decode_access_token
from app.database import get_database

settings = get_settings()


async def get_current_user(
    db: AsyncIOMotorDatabase = Depends(get_database),
    session_token: str | None = Cookie(default=None, alias=settings.cookie_name),
) -> dict[str, Any]:
    """Resolve the logged-in user from the HTTP-only session cookie.

    Raises 401 for any failure mode (missing cookie, bad/expired token,
    or a user that no longer exists) so callers can't distinguish these -
    that avoids leaking which part of auth failed.
    """
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
    )

    if not session_token:
        raise credentials_error

    user_id = decode_access_token(session_token)
    if not user_id:
        raise credentials_error

    try:
        object_id = ObjectId(user_id)
    except InvalidId:
        raise credentials_error

    user = await db.users.find_one({"_id": object_id})
    if not user:
        raise credentials_error

    return user
