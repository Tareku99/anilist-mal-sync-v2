"""Command-line interface for AniList-MAL sync."""

import logging
import sys
import time

import click
import requests

from .anilist_client import AniListClient
from .config import Settings, get_settings, validate_credentials
from .mal_client import MALClient
from .sync_engine import SyncEngine

logger = logging.getLogger(__name__)

# Constants
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
DEFAULT_SYNC_INTERVAL_MINUTES = 360  # 6 hours
CONFIG_RETRY_INTERVAL_SECONDS = 60  # 1 minute


def _require_valid_config():
    """Validate config credentials and exit if invalid."""
    is_valid, invalid_vars = validate_credentials()
    if not is_valid:
        _show_config_error(invalid_vars)


def _load_tokens(settings: Settings):
    """Load and validate tokens from file or environment.
    
    Returns:
        tuple: (anilist_token, mal_token, token_manager, refresh_mal_token)
    """
    from .oauth import TokenManager, refresh_mal_token
    
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
    
    return anilist_token, mal_token, token_manager, refresh_mal_token


def _show_config_error(invalid_vars: list[str], config_path: str = "data/config.yaml", exit_code: int = 1):
    """Display configuration error message and optionally exit."""
    logger.error("="*60)
    logger.error("❌ CONFIGURATION ERROR: Missing or invalid credentials")
    logger.error("="*60)
    logger.error("Missing/invalid variables:")
    for var in invalid_vars:
        logger.error(f"  - {var}")
    logger.error("")
    logger.error("📋 Required steps:")
    logger.error("  1. Get AniList credentials: https://anilist.co/settings/developer")
    logger.error("  2. Get MAL credentials: https://myanimelist.net/apiconfig")
    logger.error(f"  3. Edit {config_path} with your credentials")
    logger.error("")
    logger.error("💡 Make sure to replace ALL placeholder values")
    logger.error("="*60)
    if exit_code is not None:
        sys.exit(exit_code)


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
    settings = get_settings()
    setup_logging(log_level or settings.log_level)
    
    # Validate credentials are not placeholders
    _require_valid_config()

    # Override settings with CLI args
    if dry_run:
        settings.dry_run = True

    # Load tokens from file or env
    anilist_token, mal_token, token_manager, refresh_mal_token = _load_tokens(settings)

    # Validate credentials - if missing, trigger auto-auth
    if not anilist_token or not mal_token:
        logger.info("No authentication found - starting automatic OAuth flow...")
        logger.info("")
        
        # Automatically trigger authentication
        from .oauth import run_oauth_flow
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
            sys.exit(1)
        
        # Reload tokens after successful auth
        anilist_token = token_manager.get_valid_token("anilist", settings)
        mal_token = token_manager.get_valid_token("mal", settings, refresh_mal_token)
        
        if not anilist_token or not mal_token:
            logger.error("Failed to load tokens after authentication")
            sys.exit(1)
        
        logger.info("")
        logger.info("Authentication successful! Starting sync...")
        logger.info("")

    try:
        # Initialize clients
        logger.info("Initializing API clients...")
        anilist_client = AniListClient(anilist_token)
        mal_client = MALClient(mal_token)

        # Run sync
        engine = SyncEngine(anilist_client, mal_client, dry_run=settings.dry_run)
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

        # Success - exit normally
        sys.exit(0 if result.success else 1)
        
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code in (HTTP_UNAUTHORIZED, HTTP_FORBIDDEN):
            logger.error("="*60)
            logger.error("AUTHENTICATION FAILED: Tokens are invalid or expired")
            logger.error("="*60)
            logger.error("")
            logger.error("Starting automatic re-authentication...")
            logger.error("Please complete the OAuth flow in your browser.")
            logger.error("")
            
            # Automatically trigger re-authentication
            from .oauth import run_oauth_flow
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
            
            if reauth_success:
                logger.info("")
                logger.info("="*60)
                logger.info("Re-authentication successful! Retrying sync...")
                logger.info("="*60)
                
                # Reload tokens and retry sync once
                anilist_token = token_manager.get_valid_token("anilist", settings)
                mal_token = token_manager.get_valid_token("mal", settings, refresh_mal_token)
                
                try:
                    anilist_client = AniListClient(anilist_token)
                    mal_client = MALClient(mal_token)
                    engine = SyncEngine(anilist_client, mal_client, dry_run=settings.dry_run)
                    result = engine.sync(mode)
                    
                    click.echo(f"\n=== Sync Results ===")
                    click.echo(f"Mode: {mode}")
                    click.echo(f"Success: {result.success}")
                    click.echo(f"Entries synced: {result.entries_synced}")
                    click.echo(f"Entries failed: {result.entries_failed}")
                    
                    sys.exit(0 if result.success else 1)
                except Exception as retry_error:
                    logger.error(f"Sync failed after re-authentication: {retry_error}")
                    sys.exit(1)
            else:
                logger.error("")
                logger.error("="*60)
                logger.error("Re-authentication failed")
                logger.error("Please run manually: anilist-mal-sync auth")
                logger.error("="*60)
                sys.exit(1)
        else:
            raise  # Re-raise other HTTP errors
            
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
    
    # Validate credentials are not placeholders
    _require_valid_config()
    
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


@main.command()
@click.option(
    "--mode",
    type=click.Choice(["anilist-to-mal", "mal-to-anilist", "bidirectional"]),
    default="bidirectional",
    help="Sync mode: one-way or bidirectional",
)
@click.option(
    "--interval",
    type=int,
    default=DEFAULT_SYNC_INTERVAL_MINUTES,
    help=f"Sync interval in minutes (default: {DEFAULT_SYNC_INTERVAL_MINUTES} = 6 hours)",
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
    default="INFO",
    help="Logging level",
)
@click.option(
    "--wait-for-config",
    is_flag=True,
    help="Wait and retry if config is invalid (for Docker first-run)",
)
def run(mode: str, interval: int, log_level: str, wait_for_config: bool):
    """Run continuous sync at specified interval (like Docker service)."""
    import os
    
    setup_logging(log_level)
    
    # Docker first-run mode: wait for valid config
    if wait_for_config:
        retry_count = 0
        retry_interval = CONFIG_RETRY_INTERVAL_SECONDS
        
        logger.info("="*60)
        logger.info("AniList-MAL Sync - Configuration Validator")
        logger.info("="*60)
        
        while True:
            retry_count += 1
            logger.info(f"\n[Attempt #{retry_count}] Validating configuration...")
            
            # Reload config from file (user may have edited it)
            # Note: This creates a fresh Settings instance which reloads from disk
            _ = get_settings()
            
            # Check if valid
            is_valid, invalid_vars = validate_credentials()
            
            if is_valid:
                logger.info("✅ Configuration validated successfully!")
                logger.info("Starting sync service...\n")
                break  # Exit retry loop and start service
            
            # Show error and wait
            logger.error("")
            _show_config_error(invalid_vars, "/app/data/config.yaml", exit_code=None)
            logger.error("")
            logger.error("🔄 Options to apply changes:")
            logger.error(f"  • WAIT: Config will auto-reload in {retry_interval} seconds")
            logger.error("  • FASTER: Restart container to apply immediately")
            logger.error("")
            logger.error(f"⏳ Checking again in {retry_interval} seconds...")
            logger.error("="*60)
            
            time.sleep(retry_interval)
    else:
        # Normal mode: fail fast if config invalid
        # Load config first to populate os.environ
        _ = get_settings()
        is_valid, invalid_vars = validate_credentials()
        if not is_valid:
            _show_config_error(invalid_vars)
    
    # Convert minutes to seconds
    interval_seconds = interval * 60
    
    logger.info("="*60)
    logger.info("Starting AniList-MAL Sync Service")
    logger.info(f"Mode: {mode}")
    logger.info(f"Interval: {interval} minutes ({interval//60}h {interval%60}m)")
    logger.info("="*60)
    logger.info("")
    
    import os
    from pathlib import Path
    from .config import reload_settings
    run_count = 0
    config_path = Path("/app/data/config.yaml") if os.path.exists("/.dockerenv") else Path("data/config.yaml")
    last_mtime = None
    config_valid = True
    
    while True:
        # Check config file modification time
        try:
            mtime = config_path.stat().st_mtime
        except Exception:
            mtime = None
        # If config changed or first run, reload and validate
        if last_mtime != mtime:
            last_mtime = mtime
            try:
                _ = reload_settings()
                is_valid, invalid_vars = validate_credentials()
                if is_valid:
                    if not config_valid:
                        logger.info("✅ Configuration validated successfully! Resuming sync service...")
                    config_valid = True
                else:
                    logger.error("")
                    _show_config_error(invalid_vars, str(config_path), exit_code=None)
                    logger.error("")
                    logger.error("❌ Configuration invalid. Pausing sync. Waiting for fix...")
                    config_valid = False
            except Exception as e:
                logger.error(f"❌ Failed to load config: {e}")
                logger.error("❌ Configuration invalid. Pausing sync. Waiting for fix...")
                config_valid = False
        # If config is invalid, wait and retry
        if not config_valid:
            time.sleep(10)
            continue
        run_count += 1
        logger.info(f"Starting sync run #{run_count}...")
        # Directly invoke sync function (no CliRunner isolation)
        import click
        ctx = click.Context(sync)
        ctx.params = {
            'mode': mode,
            'dry_run': False,
            'log_level': log_level
        }
        try:
            with ctx:
                sync.invoke(ctx)
            logger.info(f"Sync run #{run_count} completed successfully")
        except SystemExit as e:
            if e.code == 0:
                logger.info(f"Sync run #{run_count} completed successfully")
            else:
                logger.error(f"Sync run #{run_count} failed with exit code {e.code}")
        except Exception as e:
            logger.error(f"Sync run #{run_count} failed: {e}")
        logger.info("")
        logger.info(f"Waiting {interval} minutes until next sync...")
        next_sync_time = time.localtime(time.time() + interval_seconds)
        logger.info(f"Next sync at: {time.strftime('%Y-%m-%d %H:%M:%S %Z', next_sync_time)}")
        logger.info("")
        try:
            time.sleep(interval_seconds)
        except KeyboardInterrupt:
            logger.info("")
            logger.info("="*60)
            logger.info("Service stopped by user")
            logger.info(f"Total sync runs: {run_count}")
            logger.info("="*60)
            sys.exit(0)


@main.command()
@click.option(
    "--mode",
    type=click.Choice(["anilist-to-mal", "mal-to-anilist", "bidirectional"]),
    default="bidirectional",
    help="Sync mode: one-way or bidirectional",
)
@click.option(
    "--interval",
    type=int,
    default=DEFAULT_SYNC_INTERVAL_MINUTES,
    help="Minutes between syncs",
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
    default="INFO",
    help="Logging level",
)
@click.option(
    "--port",
    type=int,
    default=8080,
    help="Web UI port",
)
@click.option(
    "--host",
    type=str,
    default="0.0.0.0",
    help="Web UI host",
)
def web(mode: str, interval: int, log_level: str, port: int, host: str):
    """Run sync service with web UI."""
    import asyncio
    import threading
    import uvicorn
    from .web import app, update_sync_status
    
    settings = get_settings()
    setup_logging(log_level or settings.log_level)
    
    logger.info("="*60)
    logger.info("AniList-MAL Sync - Web UI Mode")
    logger.info("="*60)
    logger.info(f"Web UI: http://localhost:{port}")
    logger.info(f"Sync Mode: {mode}")
    logger.info(f"Sync Interval: {interval} minutes")
    logger.info("="*60)
    logger.info("")
    
    # Validate credentials are not placeholders
    _require_valid_config()
    
    # Override settings with CLI args
    mode_override = mode
    interval_seconds = interval * 60
    
    # Start sync service in background thread
    def sync_service():
        run_count = 0
        update_sync_status(running=True)
        
        while True:
            run_count += 1
            logger.info(f"Starting sync run #{run_count}...")
            
            import click
            ctx = click.Context(sync)
            ctx.params = {
                'mode': mode_override,
                'dry_run': False,
                'log_level': log_level
            }
            
            try:
                with ctx:
                    sync.invoke(ctx)
                logger.info(f"Sync run #{run_count} completed successfully")
                update_sync_status(
                    running=True,
                    last_sync=time.strftime('%Y-%m-%d %H:%M:%S %Z'),
                    last_result="Success"
                )
            except SystemExit as e:
                result = "Success" if e.code == 0 else f"Failed (exit {e.code})"
                update_sync_status(
                    running=True,
                    last_sync=time.strftime('%Y-%m-%d %H:%M:%S %Z'),
                    last_result=result
                )
                if e.code == 0:
                    logger.info(f"Sync run #{run_count} completed successfully")
                else:
                    logger.error(f"Sync run #{run_count} failed with exit code {e.code}")
            except Exception as e:
                logger.error(f"Sync run #{run_count} failed: {e}")
                update_sync_status(
                    running=True,
                    last_sync=time.strftime('%Y-%m-%d %H:%M:%S %Z'),
                    last_result=f"Error: {str(e)}"
                )
            
            logger.info("")
            logger.info(f"Waiting {interval} minutes until next sync...")
            next_sync_time = time.localtime(time.time() + interval_seconds)
            next_sync_str = time.strftime('%Y-%m-%d %H:%M:%S %Z', next_sync_time)
            logger.info(f"Next sync at: {next_sync_str}")
            update_sync_status(next_sync=next_sync_str)
            logger.info("")
            
            try:
                time.sleep(interval_seconds)
            except KeyboardInterrupt:
                update_sync_status(running=False)
                logger.info("Sync service stopped")
                break
    
    # Start sync thread
    sync_thread = threading.Thread(target=sync_service, daemon=True)
    sync_thread.start()
    
    # Run FastAPI server (this blocks)
    try:
        uvicorn.run(app, host=host, port=port, log_level="warning")
    except KeyboardInterrupt:
        update_sync_status(running=False)
        logger.info("")
        logger.info("="*60)
        logger.info("Web UI stopped by user")
        logger.info("="*60)
        sys.exit(0)


if __name__ == "__main__":
    main()
