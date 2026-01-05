# AniList ⇄ MyAnimeList Sync

A service to synchronize anime and manga lists between AniList and MyAnimeList with support for bidirectional sync.

## Features

- **Sync Modes**:
  - AniList → MyAnimeList (one-way)
  - MyAnimeList → AniList (one-way)
  - Bidirectional sync with conflict resolution
- **Anime support** (manga coming soon)
- **Docker deployment** or manual execution
- **OAuth authentication** for both services
- **Rate limiting** and retry logic

## Quick Start

### Local Setup

```bash
# Install dependencies
pip install setuptools wheel requests click python-dotenv pydantic pydantic-settings

# Set PYTHONPATH (Windows PowerShell)
$env:PYTHONPATH="$PWD\src"

# Copy and configure credentials
Copy-Item .env.example .env
# Edit .env with your client IDs and secrets

# Run OAuth authentication (opens browser)
py -m anilist_mal_sync.cli auth

# Run sync
py -m anilist_mal_sync.cli sync --mode anilist-to-mal
```

### Docker

```bash
# Build image
docker build -t anilist-mal-sync .

# Run container
docker run --env-file .env anilist-mal-sync sync --mode anilist-to-mal
```

## Authentication

### Quick Setup (Recommended)

1. **Get API Client Credentials**:
   - **AniList**: https://anilist.co/settings/developer → Create Client
   - **MyAnimeList**: https://myanimelist.net/apiconfig → Create App

2. **Configure `.env`** *(required)*:
   ```bash
   Copy-Item .env.example .env
   ```
   
   Edit `.env` and add your credentials (**all fields required**):
   ```env
   # API Credentials (required)
   ANILIST_CLIENT_ID=your_client_id
   ANILIST_CLIENT_SECRET=your_client_secret
   MAL_CLIENT_ID=your_client_id
   MAL_CLIENT_SECRET=your_client_secret
   
   # Usernames (required)
   ANILIST_USERNAME=your_username
   MAL_USERNAME=your_username
   ```

3. **Run OAuth Flow** (opens browser, saves tokens automatically):
   ```bash
   py -m anilist_mal_sync.cli auth
   # Or authenticate with just one service:
   py -m anilist_mal_sync.cli auth --service anilist
   py -m anilist_mal_sync.cli auth --service mal
   ```

Tokens are saved to `data/tokens.json` and automatically loaded for sync operations.

## Sync Modes

- `anilist-to-mal`: One-way sync from AniList to MyAnimeList
- `mal-to-anilist`: One-way sync from MyAnimeList to AniList
- `bidirectional`: Two-way sync with conflict resolution (latest update wins)

## Configuration

Create a `.env` file or set environment variables:

```env
# OAuth Configuration (optional - defaults provided)
OAUTH_PORT=18080
OAUTH_REDIRECT_URI=http://localhost:18080/callback

# API Client Credentials (REQUIRED)
ANILIST_CLIENT_ID=your_client_id
ANILIST_CLIENT_SECRET=your_secret
MAL_CLIENT_ID=your_client_id
MAL_CLIENT_SECRET=your_secret

# Usernames (REQUIRED)
ANILIST_USERNAME=your_username
MAL_USERNAME=your_username

# Sync Options (optional - defaults provided)
SYNC_MODE=bidirectional
SCORE_SYNC_MODE=auto  # auto: normalize scores (AniList 100-point → MAL 0-10), disabled: don't sync scores
DRY_RUN=false
LOG_LEVEL=INFO

# Token Storage (optional - default: data/tokens.json)
TOKEN_FILE=data/tokens.json
```

**Required Fields:**
- Client credentials are validated when running `auth` command
- Usernames are validated when running `sync` command
- Missing required fields will cause clear error messages

**Note**: Access tokens are obtained via the `auth` command and stored in `tokens.json`.

## Token Management

### Auto-Refresh Behavior

- **MyAnimeList**: Tokens expire after **31 days** and are **automatically refreshed** using the refresh token
- **AniList**: Tokens expire after **1 year** and **require manual re-authentication** (AniList does not provide refresh tokens)

When your AniList token expires, simply run:
```bash
py -m anilist_mal_sync.cli auth --service anilist
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black src/ tests/
ruff check src/ tests/
```

## License

MIT
