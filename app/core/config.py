from functools import lru_cache

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings sourced from environment variables."""

    project_name: str = "MQDB Service"
    api_prefix: str = "/api/v1"
    mongo_uri: str = Field(
        default="mongodb://localhost:27017",
        validation_alias=AliasChoices("MQDB_MONGO_URI", "MONGO_URI"),
    )
    mongo_db_name: str = Field(
        default="mqdb",
        validation_alias=AliasChoices("MQDB_MONGO_DB_NAME", "MQDB_DB_NAME", "MONGO_DB_NAME"),
    )
    cors_origins: list[str] = Field(
        default=["*"],
        description="Comma-separated origins allowed for CORS (use '*' for all)",
        validation_alias=AliasChoices("MQDB_CORS_ORIGINS", "CORS_ORIGINS"),
    )
    api_key_salt: str = Field(..., validation_alias=AliasChoices("API_KEY_SALT", "MQDB_API_KEY_SALT"))
    demo_api_key: str | None = Field(default=None, validation_alias=AliasChoices("DEMO_API_KEY", "MQDB_DEMO_API_KEY"))
    admin_master_key: str | None = Field(
        default=None, validation_alias=AliasChoices("ADMIN_MASTER_KEY", "MQDB_ADMIN_MASTER_KEY")
    )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="allow")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, value):
        """Allow comma-separated or JSON array strings for CORS origins."""

        if isinstance(value, str):
            if value.strip() == "":
                return []
            # If provided as JSON array, let pydantic parse it
            if value.strip().startswith("["):
                return value
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings instance."""

    return Settings()
