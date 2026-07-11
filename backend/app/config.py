from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Internal Knowledge Agent"
    database_url: str = "postgresql+psycopg://knowledge:knowledge@postgres:5432/knowledge"
    jwt_secret: SecretStr = SecretStr("demo-only-change-me-at-least-32-characters")
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    anthropic_api_key: SecretStr | None = None
    chat_model: str = "claude-sonnet-4-6"
    chat_max_tokens: int = 2048
    embedding_dimensions: int = 1536
    retrieval_max_distance: float = 0.72
    document_root: str = "/data/documents"


@lru_cache
def get_settings() -> Settings:
    return Settings()
