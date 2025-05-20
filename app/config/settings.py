from enum import Enum
from functools import lru_cache

from pydantic import BaseSettings, validator
from uvicorn.config import LOG_LEVELS


class Environment(Enum):
    localdev: str = "localdev"
    dev: str = "dev"
    prod: str = "prod"


class GoogleDriveSettings(BaseSettings):
    credentials_path: str = "keys/erudite-scholar-447111-m6-d346e2fd7c8f.json"
    default_upload_path: str = "/test/files"

    class Config:
        env_prefix = "GOOGLE_DRIVE_"


class DatabaseSettings(BaseSettings):
    name: str = "fastapi_db"
    user: str = "postgres"
    password: str = "postgres"
    host: str = "localhost"
    port: int = 5432

    class Config:
        env_prefix = "POSTGRES_DB_"

    @property
    def url(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"

    @property
    def async_url(self) -> str:
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


class Settings(BaseSettings):
    environment: Environment = Environment.localdev
    service: str = "fast-api-docker-poetry"
    port: int = int("8009")
    host: str = "0.0.0.0"
    log_level: str = "debug"
    app_reload: bool = True

    ALLOWED_CORS_ORIGINS: set = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://host.docker.internal:5173",
    ]

    @property
    def code_branch(self) -> str:
        if self.environment == Environment.prod:
            return "main"
        else:
            return "dev"

    @validator("log_level")
    def valid_loglevel(cls, level: str) -> str:
        if level not in LOG_LEVELS.keys():
            raise ValueError(f"log_level must be one of {LOG_LEVELS.keys()}")
        return level

    @property
    def is_local_dev(self) -> bool:
        return self.environment == Environment.localdev


@lru_cache(maxsize=1)
def get_settings():
    return Settings()


@lru_cache()
def get_database_settings() -> DatabaseSettings:
    return DatabaseSettings()


@lru_cache()
def get_google_drive_settings() -> GoogleDriveSettings:
    return GoogleDriveSettings()
