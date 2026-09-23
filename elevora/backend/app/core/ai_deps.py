from functools import lru_cache

from app.services.ai_client import OpenAIClient


@lru_cache
def get_ai_client() -> OpenAIClient:
    return OpenAIClient()
