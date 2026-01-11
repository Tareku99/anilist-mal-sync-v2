"""Configuration management using Pydantic models."""

import logging
import os
import shutil
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


# Placeholder values that indicate unconfigured credentials
INVALID_PLACEHOLDERS = {
    "YOUR_ANILIST_CLIENT_ID_HERE",
    "YOUR_MAL_CLIENT_ID_HERE",
    "YOUR_ANILIST_CLIENT_SECRET_HERE",
    "YOUR_MAL_CLIENT_SECRET_HERE",
    "YOUR_ANILIST_USERNAME_HERE",
    "YOUR_MAL_USERNAME_HERE",
    "",
}

REQUIRED_VARS = [
    "ANILIST_CLIENT_ID",
    "ANILIST_CLIENT_SECRET",
    "ANILIST_USERNAME",
    "MAL_CLIENT_ID",
    "MAL_CLIENT_SECRET",
    "MAL_USERNAME",
]


class OAuthConfig(BaseModel):
    """OAuth configuration."""
    port: int = 18080
    redirect_uri: str = "http://localhost:18080/callback"


class AniListConfig(BaseModel):
    """AniList API configuration."""
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    username: Optional[str] = None
    auth_url: str = "https://anilist.co/api/v2/oauth/authorize"
    token_url: str = "https://anilist.co/api/v2/oauth/token"


class MALConfig(BaseModel):
    """MyAnimeList API configuration."""
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    username: Optional[str] = None
    auth_url: str = "https://myanimelist.net/v1/oauth2/authorize"
    token_url: str = "https://myanimelist.net/v1/oauth2/token"


class SyncConfig(BaseModel):
    """Synchronization settings."""
    mode: str = "bidirectional"
    score_sync_mode: str = "auto"
    dry_run: bool = False
    log_level: str = "INFO"


class Config(BaseModel):
    """Root configuration model."""
    oauth: OAuthConfig = Field(default_factory=OAuthConfig)
    anilist: AniListConfig = Field(default_factory=AniListConfig)
    mal: Optional[MALConfig] = None
    myanimelist: Optional[MALConfig] = None
    sync: SyncConfig = Field(default_factory=SyncConfig)
    token_file_path: str = "data/tokens.json"

    @field_validator("mal", "myanimelist", mode="before")
    @classmethod
    def ensure_mal_config(cls, v):
        """Ensure MAL config is a dict even if None."""
        return v if v is not None else {}


class Settings:
    """Application settings loaded from config.yaml."""

    def __init__(self):
        """Load and validate configuration."""
        self.config_path = self._get_config_path()
        
        if not self.config_path.exists():
            self._create_config_template()
        
        self._load_config()
    
    def _get_config_path(self) -> Path:
        """Get config file path based on environment."""
        if os.path.exists("/.dockerenv"):
            return Path("/app/data/config.yaml")
        return Path("data/config.yaml")
    
    def _create_config_template(self) -> None:
        """Create config template from example."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        example_path = Path("config.example.yaml")
        if example_path.exists():
            shutil.copy(example_path, self.config_path)
            logger.info(f"✅ Created config template: {self.config_path}")
            logger.info("📝 Please edit the config file with your credentials")
    
    def _load_config(self) -> None:
        """Load configuration from YAML using Pydantic."""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                raw_config = yaml.safe_load(f) or {}
            
            config = Config(**raw_config)
            logger.info(f"✅ Loaded configuration from {self.config_path}")
            
            # Map to attributes for backward compatibility
            self.oauth_port = config.oauth.port
            self.oauth_redirect_uri = config.oauth.redirect_uri
            
            self.anilist_client_id = config.anilist.client_id
            self.anilist_client_secret = config.anilist.client_secret
            self.anilist_username = config.anilist.username
            self.anilist_auth_url = config.anilist.auth_url
            self.anilist_token_url = config.anilist.token_url
            self.anilist_access_token = os.environ.get("ANILIST_ACCESS_TOKEN", "")
            
            # Support both "mal" and "myanimelist" keys
            mal_config = config.myanimelist or config.mal or MALConfig()
            self.mal_client_id = mal_config.client_id
            self.mal_client_secret = mal_config.client_secret
            self.mal_username = mal_config.username
            self.mal_auth_url = mal_config.auth_url
            self.mal_token_url = mal_config.token_url
            self.mal_access_token = os.environ.get("MAL_ACCESS_TOKEN", "")
            self.mal_refresh_token = os.environ.get("MAL_REFRESH_TOKEN", "")
            
            self.sync_mode = config.sync.mode
            self.score_sync_mode = config.sync.score_sync_mode
            self.dry_run = config.sync.dry_run
            self.log_level = config.sync.log_level
            
            self.token_file = Path(config.token_file_path)
            
            # Set environment variables for validation
            self._set_env_vars()
        
        except Exception as e:
            logger.error(f"❌ Failed to load config: {e}")
            raise
    
    def _set_env_vars(self) -> None:
        """Set environment variables from config for validation."""
        os.environ["ANILIST_CLIENT_ID"] = str(self.anilist_client_id or "")
        os.environ["ANILIST_CLIENT_SECRET"] = str(self.anilist_client_secret or "")
        os.environ["ANILIST_USERNAME"] = str(self.anilist_username or "")
        os.environ["MAL_CLIENT_ID"] = str(self.mal_client_id or "")
        os.environ["MAL_CLIENT_SECRET"] = str(self.mal_client_secret or "")
        os.environ["MAL_USERNAME"] = str(self.mal_username or "")


def validate_credentials() -> tuple[bool, list[str]]:
    """
    Validate that credentials are not placeholder values.
    Checks os.environ for required variables set by Settings class.
    Returns (is_valid, list_of_invalid_vars).
    """
    missing_or_invalid = []
    for var_name in REQUIRED_VARS:
        value = os.environ.get(var_name, "")
        if not value or value in INVALID_PLACEHOLDERS:
            missing_or_invalid.append(var_name)
    
    return len(missing_or_invalid) == 0, missing_or_invalid



# Singleton cache for settings
_SETTINGS_SINGLETON = None

def get_settings() -> Settings:
    """Get (cached) application settings singleton."""
    global _SETTINGS_SINGLETON
    if _SETTINGS_SINGLETON is None:
        _SETTINGS_SINGLETON = Settings()
    return _SETTINGS_SINGLETON

def reload_settings() -> Settings:
    """Force reload of application settings singleton."""
    global _SETTINGS_SINGLETON
    _SETTINGS_SINGLETON = Settings()
    return _SETTINGS_SINGLETON
