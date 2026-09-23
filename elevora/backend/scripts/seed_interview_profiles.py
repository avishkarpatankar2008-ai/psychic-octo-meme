"""
Seed (or re-seed) the default system Interview Profiles.

This runs automatically on every app startup (see app/main.py's lifespan) —
so in normal use you never need to run this by hand. It exists as an
explicit, scriptable entry point for deploy/migration tooling, and for
re-running against a specific database without booting the whole API.

Idempotent: safe to run any number of times against the same database.
Existing system profiles are left untouched; only missing ones are added.

Usage:
    cd backend
    source venv/bin/activate  (or however you activated your env)
    python -m scripts.seed_interview_profiles
"""

import asyncio

from motor.motor_asyncio import AsyncIOMotorClient

from app.config import get_settings
from app.database import ensure_indexes
from app.services.interview_profiles import DEFAULT_PROFILES, seed_default_profiles


async def main() -> None:
    settings = get_settings()
    client = AsyncIOMotorClient(settings.mongo_uri)
    db = client[settings.mongo_db_name]

    print(f"Connecting to {settings.mongo_uri} / db={settings.mongo_db_name!r}...")
    await ensure_indexes(db)

    inserted = await seed_default_profiles(db)
    total = await db.interview_profiles.count_documents({"isSystem": True})

    print(f"Inserted {inserted} new system profile(s) (of {len(DEFAULT_PROFILES)} defined).")
    print(f"{total} system profile(s) now present in the database.")

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
