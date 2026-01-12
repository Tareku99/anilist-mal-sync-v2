"""Health check script for Docker container."""

import sys
import logging
from pathlib import Path

from anilist_mal_sync.config import get_settings
from anilist_mal_sync.oauth import TokenManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

AUTH_INSTRUCTION = "   Run: anilist-mal-sync auth"


def main():
    """Check if tokens are valid and services are reachable."""
    try:
        settings = get_settings()
    except Exception as e:
        logger.error(f"[ERROR] UNHEALTHY: Failed to load configuration: {e}")
        sys.exit(1)
    
    # Check if token file exists
    token_file = Path(settings.token_file)
    if not token_file.exists():
        logger.error("[ERROR] UNHEALTHY: Token file not found")
        logger.error(f"   Expected: {token_file}")
        logger.error(AUTH_INSTRUCTION)
        sys.exit(1)
    
    # Use TokenManager to validate tokens (leverages existing validation logic)
    try:
        token_manager = TokenManager(settings.token_file)
        tokens_data = token_manager._load_tokens()
        
        if not tokens_data or "tokens" not in tokens_data:
            logger.error("[ERROR] UNHEALTHY: No tokens found in token file")
            logger.error(AUTH_INSTRUCTION)
            sys.exit(1)
        
        tokens = tokens_data["tokens"]
        
        # Validate we have both tokens
        if not tokens.get("anilist", {}).get("access_token"):
            logger.error("[ERROR] UNHEALTHY: AniList access token missing")
            logger.error(AUTH_INSTRUCTION)
            sys.exit(1)
        
        if not tokens.get("mal", {}).get("access_token"):
            logger.error("[ERROR] UNHEALTHY: MAL access token missing")
            logger.error(AUTH_INSTRUCTION)
            sys.exit(1)
        
        logger.info("[OK] HEALTHY: All tokens present")
        sys.exit(0)
        
    except Exception as e:
        logger.error(f"[ERROR] UNHEALTHY: Token validation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
