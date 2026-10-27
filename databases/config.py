"""One connection configuration for database tooling and Gilbert's API."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / "api" / ".env", env_file_encoding="utf-8", extra="ignore"
    )
    mysql_host: str = "127.0.0.1"
    mysql_port: int = Field(default=3307, ge=1, le=65535)
    mysql_user: str = "api_user"
    mysql_password: str = "local_api_password"
    mysql_database: str = Field(default="pjme_energy", pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    mysql_source_id: int | None = Field(default=None, ge=1)
    mongo_uri: str = "mongodb://127.0.0.1:27018"
    mongo_database: str = "pjme_energy"
    mongo_collection: str = "energy_observations"
