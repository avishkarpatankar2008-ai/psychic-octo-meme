from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import close_mongo_connection, connect_to_mongo, ensure_indexes, get_database
from app.routers import auth, interview_profiles, interviews
from app.services.interview_profiles import seed_default_profiles

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    connect_to_mongo()
    db = get_database()
    await ensure_indexes(db)
    # Idempotent: safe to run on every startup, across every worker.
    await seed_default_profiles(db)
    yield
    close_mongo_connection()


app = FastAPI(title="Elevora API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(interviews.router)
app.include_router(interview_profiles.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
