# AniList ⇄ MyAnimeList Sync

A service to synchronize anime lists between AniList and MyAnimeList with support for bidirectional sync.

## Features

- **Bidirectional sync** with conflict resolution (latest update wins)
- **One-way sync modes**: AniList → MAL or MAL → AniList
- **OAuth authentication** for both services
- **Docker deployment** with auto-configuration
- **YAML-based configuration** with validation
- **Rate limiting** and automatic retry logic

## Quick Start

### 1. Get API Credentials

You need OAuth credentials from both services:

**AniList:**
1. Visit https://anilist.co/settings/developer
2. Click "Create Client"
3. Copy the **Client ID** and **Client Secret**

**MyAnimeList:**
1. Visit https://myanimelist.net/apiconfig
2. Click "Create ID"
3. Copy the **Client ID** and **Client Secret**

### 2. Install

```bash
git clone https://github.com/yourusername/anilist-mal-sync
cd anilist-mal-sync
py install.py  # Creates venv and installs dependencies
```

### 3. Configure

```bash
# Copy template
cp config.example.yaml data/config.yaml

# Edit with your credentials
notepad data/config.yaml  # Windows
nano data/config.yaml     # Linux/macOS
```

**Minimum required config:**

```yaml
anilist:
  client_id: "your_anilist_client_id"
  client_secret: "your_anilist_client_secret"
  username: "your_anilist_username"

myanimelist:
  client_id: "your_mal_client_id"
  client_secret: "your_mal_client_secret"
  username: "your_mal_username"
```

### 4. Authenticate

```bash
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/macOS

anilist-mal-sync auth
```

This opens your browser to authorize both services and saves tokens to `data/tokens.json`.

### 5. Sync

```bash
# One-time sync
anilist-mal-sync sync --mode bidirectional

# Continuous sync (every 6 hours)
anilist-mal-sync run --interval 360
```

## Configuration

All settings are in `data/config.yaml`. The file is auto-created with placeholders on first run.

**Complete example:**

```yaml
oauth:
  port: 18080
  redirect_uri: "http://localhost:18080/callback"

anilist:
  client_id: "your_id"
  client_secret: "your_secret"
  username: "your_username"

myanimelist:  # Can also use "mal" instead
  client_id: "your_id"
  client_secret: "your_secret"
  username: "your_username"

sync:
  mode: "bidirectional"  # Options: anilist-to-mal, mal-to-anilist, bidirectional
  interval: 360          # Minutes between syncs (for run command)
  log_level: "INFO"      # Options: DEBUG, INFO, WARNING, ERROR
  dry_run: false         # If true, shows changes without applying them
```

**Notes:**
- Config uses Pydantic models for automatic validation
- Missing required fields show helpful error messages with links to credential pages
- Only required fields need to be set; optional fields have sensible defaults
- Same config file works for local dev and Docker

## Authentication

### First-Time Setup

```bash
anilist-mal-sync auth
```

Opens browser for OAuth authorization. Tokens are saved to `data/tokens.json`.

### Authenticate Individual Services

```bash
anilist-mal-sync auth --service anilist  # AniList only
anilist-mal-sync auth --service mal      # MyAnimeList only
```

### Token Expiration

- **MyAnimeList**: Tokens expire after 31 days, **auto-refresh** using refresh token
- **AniList**: Tokens expire after 1 year, requires **manual re-auth**:
  ```bash
  anilist-mal-sync auth --service anilist
  ```

## Usage

### One-Time Sync

```bash
# Bidirectional (both ways)
anilist-mal-sync sync --mode bidirectional

# One-way sync
anilist-mal-sync sync --mode anilist-to-mal
anilist-mal-sync sync --mode mal-to-anilist

# Dry run (see changes without applying)
anilist-mal-sync sync --dry-run
```

### Continuous Sync

```bash
# Every 6 hours (default)
anilist-mal-sync run

# Custom interval (in minutes)
anilist-mal-sync run --interval 60  # Every hour
anilist-mal-sync run --interval 1440  # Daily
```

Press `Ctrl+C` to stop.

## Docker Deployment

### Quick Start

```bash
docker-compose up -d
```

### First-Run Behavior

On first run, the container:
1. Creates `data/config.yaml` with placeholder values
2. Shows error asking you to edit credentials
3. Waits for valid config (checks every 60 seconds)

**Configure your credentials:**

```bash
# Edit the auto-created config
nano data/config.yaml
```

**Apply changes:**
- **Fast**: `docker-compose restart`
- **Auto**: Wait 60 seconds for auto-reload

### Volumes

```yaml
volumes:
  - ./data:/app/data  # Contains config.yaml and tokens.json
```

### Authentication in Docker

When tokens are missing or expired, the container automatically:
1. Shows OAuth URLs in logs
2. Waits for you to authorize in browser
3. Resumes syncing after authentication

**Manual re-auth (if needed):**
```bash
docker-compose run --rm sync auth
```

### Health Check

```bash
# Check token validity
docker exec anilist-mal-sync-v2-sync-1 python -m anilist_mal_sync.healthcheck

# View status
docker ps
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

**Project Structure:**
```
src/anilist_mal_sync/
├── config.py          # Pydantic-based YAML configuration
├── cli.py             # Click CLI commands
├── anilist_client.py  # AniList API client
├── mal_client.py      # MyAnimeList API client
├── sync_engine.py     # Sync logic and conflict resolution
└── oauth.py           # OAuth flow and token management
```

## Troubleshooting

**Authentication fails:**
```bash
rm data/tokens.json
anilist-mal-sync auth
```

**Rate limit errors:**
Wait 60 seconds and retry. The sync engine has built-in rate limiting.

**Config validation errors:**
Check that:
- All placeholder values (e.g., "YOUR_CLIENT_ID_HERE") are replaced
- Client IDs and secrets are correct
- Usernames match your actual accounts

## License

MIT
