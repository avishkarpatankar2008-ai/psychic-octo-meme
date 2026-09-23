from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserPreferences(BaseModel):
    language: str = "English"
    defaultDifficulty: str = "medium"


class UserPublic(BaseModel):
    """What we ever return to the client. Never include passwordHash here."""

    id: str
    email: EmailStr
    name: str
    createdAt: datetime
    preferences: UserPreferences = Field(default_factory=UserPreferences)
