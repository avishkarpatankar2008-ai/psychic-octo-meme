from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import get_settings

settings = get_settings()

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


def connect_to_mongo() -> None:
    """Create the Mongo client. Called once on app startup."""
    global _client, _db
    _client = AsyncIOMotorClient(settings.mongo_uri)
    _db = _client[settings.mongo_db_name]


def close_mongo_connection() -> None:
    global _client, _db
    if _client is not None:
        _client.close()
    _client = None
    _db = None


def get_database() -> AsyncIOMotorDatabase:
    """FastAPI dependency: returns the active database handle.

    Raises if called before connect_to_mongo() (i.e. before app startup),
    which should never happen in normal request handling.
    """
    if _db is None:
        raise RuntimeError("Database not initialized. Did the app start correctly?")
    return _db


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    """Create indexes required for correctness (not just performance)."""
    await db.users.create_index("email", unique=True)
    await db.interviews.create_index("userId")
    await db.interview_turns.create_index([("interviewId", 1), ("sequence", 1)])
    await db.interview_profiles.create_index([("isSystem", 1), ("name", 1)])
    await db.interview_profiles.create_index("createdBy")
