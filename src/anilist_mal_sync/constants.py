"""Constants used throughout the application."""

from enum import Enum


class SyncMode(str, Enum):
    """Sync mode options."""

    ANILIST_TO_MAL = "anilist-to-mal"
    MAL_TO_ANILIST = "mal-to-anilist"
    BIDIRECTIONAL = "bidirectional"


class ServiceName(str, Enum):
    """Service names."""

    ANILIST = "anilist"
    MAL = "mal"
    MYANIMELIST = "mal"  # Alias for MAL


# HTTP Status Codes
HTTP_OK = 200
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
HTTP_NOT_FOUND = 404

# Default values
DEFAULT_SYNC_INTERVAL_MINUTES = 360  # 6 hours
DEFAULT_OAUTH_PORT = 18080
DEFAULT_WEB_UI_PORT = 8080
CONFIG_RETRY_INTERVAL_SECONDS = 60  # 1 minute
TOKEN_EXPIRY_BUFFER_SECONDS = 300  # 5 minutes
