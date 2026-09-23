from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central app configuration, loaded from environment variables / .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "development"

    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db_name: str = "elevora"

    jwt_secret: str = "insecure-dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24

    frontend_origin: str = "http://localhost:3000"

    cookie_name: str = "elevora_session"
    cookie_samesite: str = "lax"

    # Phase 2: AI interview engine
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # Phase 3: voice
    openai_transcribe_model: str = "gpt-4o-mini-transcribe"
    openai_tts_model: str = "gpt-4o-mini-tts"
    openai_tts_voice: str = "alloy"

    @property
    def cookie_secure(self) -> bool:
        # Secure cookies require HTTPS; only enforce in non-development environments.
        return self.env != "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
