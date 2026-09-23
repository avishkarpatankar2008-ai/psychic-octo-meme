from fastapi import APIRouter, Depends, HTTPException, Response, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from app.config import get_settings
from app.core.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.database import get_database
from app.models.user import new_user_document, user_doc_to_public
from app.schemas.auth import LoginRequest, RegisterRequest
from app.schemas.user import UserPublic

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


def _set_session_cookie(response: Response, user_id: str) -> None:
    token = create_access_token(subject=user_id)
    response.set_cookie(
        key=settings.cookie_name,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    response: Response,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> UserPublic:
    doc = new_user_document(
        name=payload.name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
    )
    try:
        result = await db.users.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    doc["_id"] = result.inserted_id
    _set_session_cookie(response, str(result.inserted_id))
    return user_doc_to_public(doc)


@router.post("/login", response_model=UserPublic)
async def login(
    payload: LoginRequest,
    response: Response,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> UserPublic:
    invalid_credentials = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect email or password.",
    )

    user = await db.users.find_one({"email": payload.email.lower()})
    if not user or not verify_password(payload.password, user["passwordHash"]):
        raise invalid_credentials

    _set_session_cookie(response, str(user["_id"]))
    return user_doc_to_public(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> None:
    response.delete_cookie(key=settings.cookie_name, path="/")


@router.get("/me", response_model=UserPublic)
async def me(current_user: dict = Depends(get_current_user)) -> UserPublic:
    return user_doc_to_public(current_user)
