"""Sync service logic for executing sync operations."""

import logging
import sys
from typing import Optional

import click
import requests

from .anilist_client import AniListClient
from .config import Settings, get_settings
from .constants import HTTP_UNAUTHORIZED, HTTP_FORBIDDEN
from .mal_client import MALClient
from .models import SyncResult
from .oauth import TokenManager, refresh_mal_token, run_oauth_flow
from .sync_engine import SyncEngine

logger = logging.getLogger(__name__)


def authenticate_services(settings: Settings, token_manager: TokenManager) -> tuple[Optional[str], Optional[str]]:
    """Authenticate both services and return tokens.
    
    Returns:
        tuple: (anilist_token, mal_token) or (None, None) if failed
    """
    logger.info("No authentication found - starting automatic OAuth flow...")
    logger.info("")
    
    auth_success = True
    
    for service in ["anilist", "mal"]:
        logger.info(f"Authenticating {service.upper()}...")
        try:
            if not run_oauth_flow(service, settings, token_manager):
                logger.error(f"Failed to authenticate {service.upper()}")
                auth_success = False
        except Exception as auth_error:
            logger.error(f"Error during {service.upper()} authentication: {auth_error}")
            auth_success = False
    
    if not auth_success:
        logger.error("Authentication failed. Please try running: anilist-mal-sync auth")
        return None, None
    
    # Reload tokens after successful auth
    anilist_token = token_manager.get_valid_token("anilist", settings)
    mal_token = token_manager.get_valid_token("mal", settings, refresh_mal_token)
    
    if not anilist_token or not mal_token:
        logger.error("Failed to load tokens after authentication")
        return None, None
    
    logger.info("")
    logger.info("Authentication successful! Starting sync...")
    logger.info("")
    return anilist_token, mal_token


def reauthenticate_services(settings: Settings, token_manager: TokenManager) -> tuple[Optional[str], Optional[str]]:
    """Re-authenticate both services and return tokens.
    
    Returns:
        tuple: (anilist_token, mal_token) or (None, None) if failed
    """
    logger.error("="*60)
    logger.error("AUTHENTICATION FAILED: Tokens are invalid or expired")
    logger.error("="*60)
    logger.error("")
    logger.error("Starting automatic re-authentication...")
    logger.error("Please complete the OAuth flow in your browser.")
    logger.error("")
    
    reauth_success = True
    
    for service in ["anilist", "mal"]:
        logger.info(f"Re-authenticating {service.upper()}...")
        try:
            if not run_oauth_flow(service, settings, token_manager):
                logger.error(f"Failed to re-authenticate {service.upper()}")
                reauth_success = False
        except Exception as auth_error:
            logger.error(f"Error during {service.upper()} re-auth: {auth_error}")
            reauth_success = False
    
    if not reauth_success:
        logger.error("")
        logger.error("="*60)
        logger.error("Re-authentication failed")
        logger.error("Please run manually: anilist-mal-sync auth")
        logger.error("="*60)
        return None, None
    
    logger.info("")
    logger.info("="*60)
    logger.info("Re-authentication successful! Retrying sync...")
    logger.info("="*60)
    
    # Reload tokens after successful re-auth
    anilist_token = token_manager.get_valid_token("anilist", settings)
    mal_token = token_manager.get_valid_token("mal", settings, refresh_mal_token)
    
    return anilist_token, mal_token


def execute_sync(
    mode: str,
    dry_run: bool = False,
    settings: Optional[Settings] = None,
    anilist_token: Optional[str] = None,
    mal_token: Optional[str] = None,
    token_manager: Optional[TokenManager] = None,
) -> tuple[bool, Optional[SyncResult]]:
    """Execute a sync operation.
    
    Args:
        mode: Sync mode (anilist-to-mal, mal-to-anilist, bidirectional)
        dry_run: If True, don't make actual changes
        settings: Settings instance (will load if not provided)
        anilist_token: AniList access token (will load if not provided)
        mal_token: MAL access token (will load if not provided)
        token_manager: TokenManager instance (will create if not provided)
    
    Returns:
        tuple: (success, result) - success indicates if sync completed, result is SyncResult or None if failed
    """
    if settings is None:
        settings = get_settings()
    
    if token_manager is None:
        token_manager = TokenManager(settings.token_file)
    
    # Load tokens if not provided
    if anilist_token is None:
        anilist_token = (
            settings.anilist_access_token 
            or token_manager.get_valid_token("anilist", settings)
        )
    
    if mal_token is None:
        mal_token = (
            settings.mal_access_token 
            or token_manager.get_valid_token("mal", settings, refresh_mal_token)
        )
    
    # Authenticate if tokens are missing
    if not anilist_token or not mal_token:
        anilist_token, mal_token = authenticate_services(settings, token_manager)
        if not anilist_token or not mal_token:
            return False, None
    
    try:
        # Initialize clients
        logger.info("Initializing API clients...")
        anilist_client = AniListClient(anilist_token)
        mal_client = MALClient(mal_token)
        
        # Run sync (use dry_run parameter, not settings.dry_run)
        engine = SyncEngine(anilist_client, mal_client, dry_run=dry_run)
        result = engine.sync(mode)
        
        return True, result
        
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code in (HTTP_UNAUTHORIZED, HTTP_FORBIDDEN):
            # Try re-authentication once
            anilist_token, mal_token = reauthenticate_services(settings, token_manager)
            if not anilist_token or not mal_token:
                return False, None
            
            # Retry sync after re-authentication
            try:
                anilist_client = AniListClient(anilist_token)
                mal_client = MALClient(mal_token)
                engine = SyncEngine(anilist_client, mal_client, dry_run=dry_run)
                result = engine.sync(mode)
                return True, result
            except Exception as retry_error:
                logger.error(f"Sync failed after re-authentication: {retry_error}")
                return False, None
        else:
            raise  # Re-raise other HTTP errors
            
    except Exception as e:
        logger.exception("Sync failed with error")
        raise


def print_sync_results(result, mode: str):
    """Print sync results to console."""
    if result.dry_run:
        click.echo("\n=== DRY RUN - No changes were made ===")
    
    click.echo(f"\n=== Sync Results ===")
    click.echo(f"Mode: {mode}")
    click.echo(f"Success: {result.success}")
    click.echo(f"Entries synced: {result.entries_synced}")
    click.echo(f"Entries failed: {result.entries_failed}")
    
    if result.errors:
        click.echo(f"\nErrors ({len(result.errors)}):")
        for error in result.errors[:10]:  # Show first 10
            click.echo(f"  - {error}")
