# Security Policy

## Supported Versions

We actively support security updates for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| Latest  | :white_check_mark: |
| < Latest| :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in AniList-MAL Sync, please **do not** open a public issue. Security vulnerabilities could affect users' OAuth tokens, API credentials, or personal anime list data.

Please report it privately using one of these methods:

1. **GitHub Security Advisory** (Preferred): Use GitHub's [Private Vulnerability Reporting](https://github.com/Tareku99/anilist-mal-sync/security/advisories/new) feature
2. **Private Issue**: Open a GitHub issue with the `[SECURITY]` label - maintainers will make it private

### What to Include

When reporting a vulnerability, please include:

- **Description**: Clear description of the security issue
- **Affected Components**: Which part of the system is affected (OAuth flow, token storage, API clients, config handling, etc.)
- **Steps to Reproduce**: Detailed steps to reproduce the vulnerability
- **Potential Impact**: What could an attacker do? (e.g., access tokens, modify lists, steal credentials)
- **Severity**: Your assessment of severity (Critical, High, Medium, Low)
- **Suggested Fix**: If you have ideas for how to fix it
- **Proof of Concept**: If applicable, a minimal example demonstrating the issue (be careful not to include real credentials)

### Response Timeline

- **Initial Response**: Within 48 hours
- **Status Update**: Within 7 days
- **Resolution**: Depends on severity and complexity

### Security Best Practices for AniList-MAL Sync

When deploying or using this project:

1. **Never commit tokens or credentials** to version control
   - The `data/tokens.json` file contains OAuth tokens - add it to `.gitignore`
   - The `data/config.yaml` file contains API credentials - never commit it
   - Use `config.example.yaml` as a template, not for actual credentials

2. **File Permissions**
   - Set `data/tokens.json` to `600` (read/write for owner only): `chmod 600 data/tokens.json`
   - Set `data/config.yaml` to `600`: `chmod 600 data/config.yaml`
   - In Docker, ensure the data volume has proper permissions

3. **OAuth Configuration**
   - **Review OAuth redirect URIs** - ensure they match your deployment exactly (no trailing slashes, correct protocol)
   - **Use HTTPS** for all OAuth callbacks in production (never use HTTP in production)
   - For local development, `http://localhost:18080/callback` is acceptable
   - For production, use your actual server IP/domain: `https://your-domain.com:18080/callback`

4. **API Credentials**
   - Keep your AniList and MyAnimeList client IDs and secrets secure
   - Rotate credentials if they are ever exposed
   - Use different OAuth apps for development and production if possible

5. **Docker Security**
   - Run containers with non-root user when possible
   - Use Docker secrets or environment variables for sensitive data
   - Keep the Docker image updated to the latest version

6. **Network Security**
   - If exposing the web UI (port 8080), consider using a reverse proxy with authentication
   - The OAuth callback port (18080) should only be accessible during initial setup
   - Consider firewall rules to restrict access to the OAuth callback port

### Known Security Considerations

#### OAuth Token Storage
- **Location**: Tokens are stored in `data/tokens.json` in JSON format
- **Contents**: Contains `access_token`, `refresh_token` (MAL only), and `expires_at` for both AniList and MyAnimeList
- **Permissions**: Set file permissions to `600` (owner read/write only)
- **Backup**: If backing up, ensure backups are encrypted and secure
- **Token Expiry**: 
  - MyAnimeList tokens expire after 31 days (auto-refreshed)
  - AniList tokens expire after 1 year (manual re-auth required)

#### Configuration File Security
- **Location**: `data/config.yaml` contains all API credentials
- **Contents**: AniList and MyAnimeList client IDs, client secrets, usernames, and OAuth settings
- **Permissions**: Set file permissions to `600`
- **Environment Variables**: Consider using environment variables for sensitive values (see `config.py` for supported env vars)

#### OAuth Flow Security
- **Callback Port**: Default OAuth callback port is `18080` - ensure this is not publicly accessible after initial setup
- **Redirect URI Validation**: Both AniList and MyAnimeList validate redirect URIs - they must match exactly
- **Token Scope**: The application requests minimal necessary permissions (read/write anime list data only)

#### API Communication
- **HTTPS Required**: All API communication uses HTTPS (AniList GraphQL, MyAnimeList REST)
- **Rate Limiting**: The application implements rate limiting and retry logic to respect API limits
- **No Data Storage**: The application does not store your anime list data - it only syncs between services

#### Docker Deployment
- **Volume Mounts**: The `data/` directory is mounted as a volume - ensure host permissions are secure
- **Network**: Container needs outbound HTTPS access to `anilist.co` and `myanimelist.net`
- **Ports**: 
  - `8080` (web UI) - consider restricting access
  - `18080` (OAuth callback) - should only be accessible during setup

#### Web UI Security
- **No Authentication**: The web UI (port 8080) currently has no authentication - restrict network access
- **Local Access Only**: Recommended to only expose on localhost or use a reverse proxy with authentication
- **Configuration Editing**: The web UI can edit `config.yaml` - ensure proper access controls

## Security Updates

Security updates will be released as patches to the latest version. We recommend:

- Regularly updating to the latest version
- Monitoring the repository for security advisories
- Subscribing to release notifications
