from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: Literal["development", "production", "test"] = "development"

    postgres_user: str = "budget"
    postgres_password: SecretStr = SecretStr("budget")
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "budget"
    postgres_test_db: str | None = None  # defaults to "<postgres_db>_test"

    secret_key: SecretStr = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7
    cookie_name: str = "budget_session"

    @property
    def database_url(self) -> str:
        return self._url(self.postgres_db)

    @property
    def test_database_url(self) -> str:
        return self._url(self.postgres_test_db or f"{self.postgres_db}_test")

    @property
    def maintenance_url(self) -> str:
        """Server-level connection, used to create databases."""
        return self._url("postgres")

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    def _url(self, db: str) -> str:
        password = self.postgres_password.get_secret_value()
        return (
            f"postgresql+psycopg://{self.postgres_user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
