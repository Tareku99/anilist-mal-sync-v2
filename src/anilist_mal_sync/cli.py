"""Command-line interface for AniList-MAL sync."""

import logging
import sys

import click

from .anilist_client import AniListClient
from .config import get_settings
from .mal_client import MALClient
from .sync_engine import SyncEngine

logger = logging.getLogger(__name__)


def setup_logging(level: str):
    """Configure logging for the application."""
    logging.basicConfig(
        level=getattr(logging, level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )


@click.group()
@click.version_option(version="0.1.0")
def main():
    """AniList to MyAnimeList sync service."""
    pass


@main.command()
@click.option(
    "--mode",
    type=click.Choice(["anilist-to-mal", "mal-to-anilist", "bidirectional"]),
    default="bidirectional",
    help="Sync mode: one-way or bidirectional",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Simulate sync without making changes",
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
    default="INFO",
    help="Logging level",
)
def sync(mode: str, dry_run: bool, log_level: str):
    """Sync anime lists between AniList and MyAnimeList."""
    from .oauth import TokenManager, refresh_mal_token

    settings = get_settings()
    setup_logging(log_level or settings.log_level)

    logger = logging.getLogger(__name__)
    
    # Validate required configuration
    if not settings.anilist_username:
        logger.error("ANILIST_USERNAME not configured in .env file")
        sys.exit(1)
    if not settings.mal_username:
        logger.error("MAL_USERNAME not configured in .env file")
        sys.exit(1)

    # Override settings with CLI args
    if dry_run:
        settings.dry_run = True

    # Load tokens from file or env
    token_manager = TokenManager(settings.token_file)
    
    # Get valid tokens (auto-refresh if needed)
    anilist_token = (
        settings.anilist_access_token 
        or token_manager.get_valid_token("anilist", settings)
    )
    mal_token = (
        settings.mal_access_token 
        or token_manager.get_valid_token("mal", settings, refresh_mal_token)
    )

    # Validate credentials
    if not anilist_token:
        logger.error("AniList access token not found. Run: anilist-mal-sync auth")
        sys.exit(1)

    if not mal_token:
        logger.error("MyAnimeList access token not found. Run: anilist-mal-sync auth")
        sys.exit(1)

    # Initialize clients
    logger.info("Initializing API clients...")
    anilist_client = AniListClient(anilist_token)
    mal_client = MALClient(mal_token)

    # Run sync
    engine = SyncEngine(anilist_client, mal_client, dry_run=settings.dry_run)

    try:
        result = engine.sync(mode)

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

        sys.exit(0 if result.success else 1)

    except Exception as e:
        logger.exception("Sync failed with error")
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option(
    "--service",
    type=click.Choice(["anilist", "mal", "both"]),
    default="both",
    help="Which service to authenticate with",
)
def auth(service: str):
    """Interactive authentication setup for AniList and MyAnimeList."""
    from .oauth import TokenManager, run_oauth_flow

    settings = get_settings()
    setup_logging("INFO")
    
    logger = logging.getLogger(__name__)
    
    # Validate required configuration based on service
    if service in ["anilist", "both"]:
        if not settings.anilist_client_id or not settings.anilist_client_secret:
            logger.error("ANILIST_CLIENT_ID and ANILIST_CLIENT_SECRET must be configured in .env file")
            sys.exit(1)
    
    if service in ["mal", "both"]:
        if not settings.mal_client_id or not settings.mal_client_secret:
            logger.error("MAL_CLIENT_ID and MAL_CLIENT_SECRET must be configured in .env file")
            sys.exit(1)
    
    click.echo("=== OAuth Authentication Setup ===\n")
    
    # Initialize token manager
    token_manager = TokenManager(settings.token_file)

    # Authenticate with selected service(s)
    success = True
    
    if service in ["anilist", "both"]:
        if not run_oauth_flow("anilist", settings, token_manager):
            success = False
            click.echo("❌ AniList authentication failed", err=True)
    
    if service in ["mal", "both"]:
        if not run_oauth_flow("mal", settings, token_manager):
            success = False
            click.echo("❌ MyAnimeList authentication failed", err=True)
    
    if success:
        click.echo(f"\n✅ Authentication complete! Tokens saved to {settings.token_file}")
        click.echo("\nYou can now run: anilist-mal-sync sync")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
