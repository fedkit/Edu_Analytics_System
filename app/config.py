"""Application configuration loaded from environment variables."""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # PostgreSQL
    postgres_host: str = "/var/run/postgresql"
    postgres_port: int = 5432
    postgres_user: str = "fedor"
    postgres_password: str = ""
    postgres_db: str = "university_db"

    # ClickHouse
    clickhouse_host: str = "localhost"
    clickhouse_port: int = 8123
    clickhouse_user: str = "default"
    clickhouse_password: str = ""
    clickhouse_database: str = "edu_analytics"

    # App
    app_title: str = "Electronic University Analytics"
    app_env: str = "development"
    log_level: str = "INFO"
    cache_ttl_seconds: int = 300

    @property
    def postgres_url(self) -> str:
        if self.postgres_host.startswith("/"):
            return (
                f"postgresql+psycopg2://{self.postgres_user}"
                f"@/{self.postgres_db}"
                f"?host={self.postgres_host}"
            )
        pw = f":{self.postgres_password}" if self.postgres_password else ""
        return (
            f"postgresql+psycopg2://{self.postgres_user}{pw}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
