"""
Central configuration. Every other module imports `settings` from here
instead of calling os.environ directly — one source of truth.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Database ---
    database_url: str = "postgresql://t2sql:t2sql_password@localhost:5432/t2sql"

    # --- Ollama ---
    ollama_base_url: str = "http://localhost:11434"
    ollama_sql_model: str = "qwen2.5-coder:3b"
    ollama_complex_model: str = "qwen2.5-coder:7b"
    ollama_embed_model: str = "nomic-embed-text"

    # --- Safety ---
    max_estimated_rows: int = 1_000_000
    query_timeout_seconds: int = 10
    max_sql_retries: int = 3

    # --- App ---
    log_level: str = "INFO"


settings = Settings()
