"""
Web UI for AniList-MAL Sync
Provides a simple dashboard for monitoring and controlling the sync service.
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional
import yaml

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .config import Settings

logger = logging.getLogger(__name__)

app = FastAPI(title="AniList-MAL Sync", version="0.1.0")

# Global state for sync status
sync_status = {
    "running": False,
    "last_sync": None,
    "next_sync": None,
    "last_result": None,
    "total_syncs": 0,
}


def _get_config_path() -> Path:
    """Get config file path based on environment (same logic as Settings class)."""
    if os.path.exists("/.dockerenv"):
        return Path("/app/data/config.yaml")
    return Path("data/config.yaml")


class SyncStatus(BaseModel):
    """Sync status response model"""
    running: bool
    last_sync: Optional[str] = None
    next_sync: Optional[str] = None
    last_result: Optional[str] = None
    total_syncs: int


class ConfigUpdate(BaseModel):
    """Config update request model"""
    config: str


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Main dashboard page"""
    html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AniList-MAL Sync Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        .header {
            text-align: center;
            color: white;
            margin-bottom: 30px;
        }
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        .header p {
            opacity: 0.9;
        }
        .cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .card {
            background: white;
            border-radius: 12px;
            padding: 25px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
        }
        .card h2 {
            color: #667eea;
            margin-bottom: 15px;
            font-size: 1.3em;
        }
        .status-item {
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid #eee;
        }
        .status-item:last-child {
            border-bottom: none;
        }
        .status-label {
            font-weight: 600;
            color: #555;
        }
        .status-value {
            color: #333;
        }
        .status-running {
            color: #10b981;
            font-weight: bold;
        }
        .status-stopped {
            color: #ef4444;
            font-weight: bold;
        }
        .btn {
            display: inline-block;
            padding: 12px 24px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 16px;
            font-weight: 600;
            text-decoration: none;
            transition: background 0.2s;
            width: 100%;
            margin-top: 10px;
        }
        .btn:hover {
            background: #5568d3;
        }
        .btn:disabled {
            background: #ccc;
            cursor: not-allowed;
        }
        .btn-secondary {
            background: #764ba2;
        }
        .btn-secondary:hover {
            background: #643a8a;
        }
        .config-editor {
            width: 100%;
            height: 400px;
            font-family: 'Courier New', monospace;
            font-size: 14px;
            padding: 15px;
            border: 2px solid #e5e7eb;
            border-radius: 6px;
            resize: vertical;
        }
        .config-editor:focus {
            outline: none;
            border-color: #667eea;
        }
        .message {
            padding: 12px;
            border-radius: 6px;
            margin-top: 15px;
            display: none;
        }
        .message.success {
            background: #d1fae5;
            color: #065f46;
            border: 1px solid #10b981;
        }
        .message.error {
            background: #fee2e2;
            color: #991b1b;
            border: 1px solid #ef4444;
        }
        .message.show {
            display: block;
        }
        .footer {
            text-align: center;
            color: white;
            margin-top: 30px;
            opacity: 0.8;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔄 AniList-MAL Sync</h1>
            <p>Monitor and control your anime list synchronization</p>
        </div>

        <div class="cards">
            <div class="card">
                <h2>📊 Status</h2>
                <div class="status-item">
                    <span class="status-label">Service:</span>
                    <span class="status-value" id="status-running">Loading...</span>
                </div>
                <div class="status-item">
                    <span class="status-label">Last Sync:</span>
                    <span class="status-value" id="status-last-sync">-</span>
                </div>
                <div class="status-item">
                    <span class="status-label">Next Sync:</span>
                    <span class="status-value" id="status-next-sync">-</span>
                </div>
                <div class="status-item">
                    <span class="status-label">Last Result:</span>
                    <span class="status-value" id="status-last-result">-</span>
                </div>
                <div class="status-item">
                    <span class="status-label">Total Syncs:</span>
                    <span class="status-value" id="status-total-syncs">0</span>
                </div>
                <button class="btn" id="refresh-btn" onclick="refreshStatus()">🔄 Refresh Status</button>
                <button class="btn btn-secondary" id="sync-now-btn" onclick="triggerSync()">▶️ Sync Now</button>
            </div>

            <div class="card">
                <h2>⚙️ Configuration</h2>
                <textarea class="config-editor" id="config-editor" placeholder="Loading configuration..."></textarea>
                <button class="btn" onclick="loadConfig()">📥 Reload Config</button>
                <button class="btn btn-secondary" onclick="saveConfig()">💾 Save Config</button>
                <div class="message" id="config-message"></div>
            </div>
        </div>

        <div class="footer">
            <p>AniList-MAL Sync v0.1.0 | Made with ❤️</p>
        </div>
    </div>

    <script>
        // Load status on page load
        window.addEventListener('DOMContentLoaded', () => {
            refreshStatus();
            loadConfig();
            // Auto-refresh every 30 seconds
            setInterval(refreshStatus, 30000);
        });

        async function refreshStatus() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                
                document.getElementById('status-running').textContent = data.running ? 'Running' : 'Stopped';
                document.getElementById('status-running').className = data.running ? 'status-value status-running' : 'status-value status-stopped';
                document.getElementById('status-last-sync').textContent = data.last_sync || '-';
                document.getElementById('status-next-sync').textContent = data.next_sync || '-';
                document.getElementById('status-last-result').textContent = data.last_result || '-';
                document.getElementById('status-total-syncs').textContent = data.total_syncs;
            } catch (error) {
                console.error('Failed to fetch status:', error);
            }
        }

        async function loadConfig() {
            try {
                const response = await fetch('/api/config');
                const data = await response.json();
                document.getElementById('config-editor').value = data.config;
                showMessage('config-message', 'Configuration loaded successfully', 'success');
            } catch (error) {
                console.error('Failed to load config:', error);
                showMessage('config-message', 'Failed to load configuration', 'error');
            }
        }

        async function saveConfig() {
            const config = document.getElementById('config-editor').value;
            try {
                const response = await fetch('/api/config', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ config }),
                });
                
                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.detail || 'Failed to save config');
                }
                
                showMessage('config-message', 'Configuration saved successfully! Restart required.', 'success');
            } catch (error) {
                console.error('Failed to save config:', error);
                showMessage('config-message', error.message, 'error');
            }
        }

        async function triggerSync() {
            const btn = document.getElementById('sync-now-btn');
            btn.disabled = true;
            btn.textContent = '⏳ Syncing...';
            
            try {
                const response = await fetch('/api/sync/trigger', { method: 'POST' });
                if (!response.ok) throw new Error('Sync failed');
                
                setTimeout(() => {
                    refreshStatus();
                    btn.disabled = false;
                    btn.textContent = '▶️ Sync Now';
                }, 3000);
            } catch (error) {
                console.error('Failed to trigger sync:', error);
                btn.disabled = false;
                btn.textContent = '▶️ Sync Now';
            }
        }

        function showMessage(elementId, message, type) {
            const msgEl = document.getElementById(elementId);
            msgEl.textContent = message;
            msgEl.className = `message ${type} show`;
            setTimeout(() => {
                msgEl.classList.remove('show');
            }, 5000);
        }
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)


@app.get("/api/status")
async def get_status() -> SyncStatus:
    """Get current sync status"""
    return SyncStatus(**sync_status)


@app.get("/api/config")
async def get_config():
    """Get current configuration (read-only)"""
    try:
        config_path = _get_config_path()
        
        if not config_path.exists():
            raise HTTPException(status_code=404, detail="Config file not found")
        
        with open(config_path, "r") as f:
            config_content = f.read()
        
        return {"config": config_content}
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/config")
async def update_config(data: ConfigUpdate):
    """Update configuration file"""
    try:
        # Validate YAML syntax
        try:
            yaml.safe_load(data.config)
        except yaml.YAMLError as e:
            raise HTTPException(status_code=400, detail=f"Invalid YAML: {str(e)}")
        
        config_path = _get_config_path()
        
        # Backup existing config
        if config_path.exists():
            backup_path = config_path.parent / "config.yaml.backup"
            with open(config_path, "r") as f:
                backup_content = f.read()
            with open(backup_path, "w") as f:
                f.write(backup_content)
        
        # Write new config
        with open(config_path, "w") as f:
            f.write(data.config)
        
        # Validate the new config can be loaded
        try:
            Settings()
        except Exception as e:
            # Restore backup if validation fails
            if backup_path.exists():
                with open(backup_path, "r") as f:
                    backup_content = f.read()
                with open(config_path, "w") as f:
                    f.write(backup_content)
            raise HTTPException(status_code=400, detail=f"Invalid configuration: {str(e)}")
        
        return {"message": "Configuration updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/sync/trigger")
async def trigger_sync():
    """Trigger an immediate sync (placeholder for now)"""
    # This will be implemented when we integrate with the CLI sync loop
    sync_status["last_sync"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sync_status["total_syncs"] += 1
    return {"message": "Sync triggered (manual implementation pending)"}


def update_sync_status(running: bool = False, last_sync: str = None, 
                       next_sync: str = None, last_result: str = None):
    """Update the global sync status (called from CLI)"""
    sync_status["running"] = running
    if last_sync:
        sync_status["last_sync"] = last_sync
    if next_sync:
        sync_status["next_sync"] = next_sync
    if last_result:
        sync_status["last_result"] = last_result
        sync_status["total_syncs"] += 1
