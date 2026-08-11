from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://localhost/babynames"
    supabase_project_ref: str = ""
    supabase_url: str = ""
    supabase_anon_key: str = ""
    cors_origins: str = "http://localhost:5173"
    rate_limit_per_hour: int = 1000

    model_config = SettingsConfigDict(
        env_file=[
            Path(__file__).resolve().parents[3] / "secrets" / ".env",
            Path(__file__).resolve().parents[2] / ".env",
        ],
        env_file_encoding="utf-8",
        extra="ignore",
    )

settings = Settings()  # type: ignore[call-arg]
