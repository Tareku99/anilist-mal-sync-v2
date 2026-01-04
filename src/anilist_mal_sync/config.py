"""Configuration management using Pydantic settings."""

from pathlib import Path
from typing import Literal, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # OAuth configuration
    oauth_port: int = Field(default=18080, alias="OAUTH_PORT")
    oauth_redirect_uri: str = Field(
        default="http://localhost:18080/callback", alias="OAUTH_REDIRECT_URI"
    )

    # AniList credentials
    anilist_client_id: Optional[str] = Field(default=None, alias="ANILIST_CLIENT_ID")
    anilist_client_secret: Optional[str] = Field(default=None, alias="ANILIST_CLIENT_SECRET")
    anilist_auth_url: str = Field(
        default="https://anilist.co/api/v2/oauth/authorize", alias="ANILIST_AUTH_URL"
    )
    anilist_token_url: str = Field(
        default="https://anilist.co/api/v2/oauth/token", alias="ANILIST_TOKEN_URL"
    )
    anilist_username: Optional[str] = Field(default=None, alias="ANILIST_USERNAME")
    anilist_access_token: str = Field(default="", alias="ANILIST_ACCESS_TOKEN")

    # MyAnimeList credentials
    mal_client_id: Optional[str] = Field(default=None, alias="MAL_CLIENT_ID")
    mal_client_secret: Optional[str] = Field(default=None, alias="MAL_CLIENT_SECRET")
    mal_auth_url: str = Field(
        default="https://myanimelist.net/v1/oauth2/authorize", alias="MAL_AUTH_URL"
    )
    mal_token_url: str = Field(
        default="https://myanimelist.net/v1/oauth2/token", alias="MAL_TOKEN_URL"
    )
    mal_username: Optional[str] = Field(default=None, alias="MAL_USERNAME")
    mal_access_token: str = Field(default="", alias="MAL_ACCESS_TOKEN")
    mal_refresh_token: str = Field(default="", alias="MAL_REFRESH_TOKEN")

    # Sync configuration
    sync_mode: Literal["anilist-to-mal", "mal-to-anilist", "bidirectional"] = Field(
        default="bidirectional", alias="SYNC_MODE"
    )
    score_sync_mode: Literal["auto", "disabled"] = Field(
        default="auto", alias="SCORE_SYNC_MODE"
    )
    dry_run: bool = Field(default=False, alias="DRY_RUN")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO", alias="LOG_LEVEL"
    )

    # Token storage
    token_file: Path = Field(default=Path("data/tokens.json"), alias="TOKEN_FILE")


def get_settings() -> Settings:
    """Get application settings singleton."""
    return Settings()
