from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    worker_concurrency: int = Field(default=5, ge=1)
    worker_metrics_port: int = 8001
    database_url: str = "postgresql+asyncpg://postgres:postgres@postgres:5432/preauth_db"
    redis_url: str = "redis://redis:6379/0"
    llm_provider: str = "stub"
    llm_api_key: str = ""
    llm_model: str = ""
    llm_base_url: str = "http://llm-stub:8080"
    stub_delay_ms: int = Field(default=250, ge=0)
    stub_jitter_ms: int = Field(default=50, ge=0)
    fault_mode: str = "none"
    corpus_raw_dir: str = "/app/corpus/raw"
    index_storage_dir: str = "/app/index_data"
    local_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    max_steps: int = Field(default=12, ge=3)
    max_tool_calls: int = Field(default=10, ge=1)
    run_timeout_s: float = Field(default=90, gt=0)
    llm_timeout_s: float = Field(default=20, gt=0)
    tool_timeout_s: float = Field(default=5, gt=0)
    max_replans: int = Field(default=2, ge=0)


@lru_cache
def get_settings() -> Settings:
    return Settings()
