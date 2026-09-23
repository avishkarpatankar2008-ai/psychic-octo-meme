from datetime import datetime, timezone
from typing import Any

from app.schemas.user import UserPublic


def new_user_document(name: str, email: str, hashed_password: str) -> dict[str, Any]:
    return {
        "name": name,
        "email": email.lower(),
        "passwordHash": hashed_password,
        "createdAt": datetime.now(timezone.utc),
        "preferences": {"language": "English", "defaultDifficulty": "medium"},
    }


def user_doc_to_public(doc: dict[str, Any]) -> UserPublic:
    return UserPublic(
        id=str(doc["_id"]),
        email=doc["email"],
        name=doc["name"],
        createdAt=doc["createdAt"],
        preferences=doc.get("preferences", {}),
    )
