"""
Web UI for AniList-MAL Sync
Provides a simple dashboard for monitoring and controlling the sync service.
"""

import logging
import os
import threading
import time
from pathlib import Path
from typing import Optional
import yaml

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .config import Settings, get_settings, reload_settings
from .sync_service import execute_sync

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

# Threading lock to prevent concurrent syncs
_sync_lock = threading.Lock()

# Store CLI sync mode and dry_run (set by CLI when web UI starts)
_cli_sync_mode = None
_cli_dry_run = None


def _get_config_path() -> Path:
    """Get config file path based on environment."""
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
    sync_in_progress: bool = False  # True if any sync (scheduled or manual) is running


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
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        .header {
            text-align: center;
            color: white;
            margin-bottom: 30px;
        }
        .header h1 { font-size: 2.5em; margin-bottom: 10px; }
        .header p { opacity: 0.9; }
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
        .status-item:last-child { border-bottom: none; }
        .status-label { font-weight: 600; color: #555; }
        .status-value { color: #333; }
        .status-running { color: #10b981; font-weight: bold; }
        .status-stopped { color: #ef4444; font-weight: bold; }
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
            transition: background 0.2s;
            width: 100%;
            margin-top: 10px;
        }
        .btn:hover:not(:disabled) { background: #5568d3; }
        .btn:disabled {
            background: #ccc;
            cursor: not-allowed;
            opacity: 0.6;
        }
        .btn-secondary { background: #764ba2; }
        .btn-secondary:hover:not(:disabled) { background: #643a8a; }
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
        .message.show { display: block; }
        .info-note {
            padding: 12px;
            background: #eff6ff;
            color: #1e3a8a;
            border: 1px solid #3b82f6;
            border-radius: 6px;
            margin-top: 15px;
            font-size: 14px;
            line-height: 1.5;
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
                <button class="btn btn-secondary" id="sync-now-btn" onclick="triggerSync(event)">▶️ Sync Now</button>
                <button class="btn" id="refresh-btn" onclick="refreshStatus()">🔄 Refresh Status</button>
            </div>

            <div class="card">
                <h2>⚙️ Configuration</h2>
                <textarea class="config-editor" id="config-editor" placeholder="Loading configuration..."></textarea>
                <button class="btn" onclick="loadConfig()">📥 Reload Config</button>
                <button class="btn btn-secondary" onclick="saveConfig()">💾 Save Config</button>
                <div class="message" id="config-message"></div>
                <div class="info-note">
                    ℹ️ <strong>Note:</strong> Most configuration changes are automatically reloaded. CLI parameters (interval, port, host) require a manual restart.
                </div>
            </div>
        </div>

        <div class="footer">
            <p>AniList-MAL Sync v0.1.0 | Made with ❤️</p>
        </div>
    </div>

    <script>
        // Status update function - updates all status fields and button states
        async function updateStatus() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                
                // Update status fields
                document.getElementById('status-running').textContent = data.running ? 'Running' : 'Stopped';
                document.getElementById('status-running').className = data.running ? 'status-value status-running' : 'status-value status-stopped';
                document.getElementById('status-last-sync').textContent = data.last_sync || '-';
                document.getElementById('status-next-sync').textContent = data.next_sync || '-';
                document.getElementById('status-last-result').textContent = data.last_result || '-';
                document.getElementById('status-total-syncs').textContent = data.total_syncs;
                
                // Update sync button state
                const syncBtn = document.getElementById('sync-now-btn');
                syncBtn.disabled = data.sync_in_progress;
                syncBtn.textContent = data.sync_in_progress ? '⏳ Syncing...' : '▶️ Sync Now';
            } catch (error) {
                console.error('Failed to fetch status:', error);
            }
        }

        // Refresh status with button feedback
        async function refreshStatus() {
            const btn = document.getElementById('refresh-btn');
            const originalText = btn.textContent;
            btn.disabled = true;
            btn.textContent = '🔄 Refreshing...';
            
            try {
                await updateStatus();
            } finally {
                setTimeout(() => {
                    btn.disabled = false;
                    btn.textContent = originalText;
                }, 300);
            }
        }

        // Load configuration
        async function loadConfig() {
            try {
                const response = await fetch('/api/config');
                const data = await response.json();
                document.getElementById('config-editor').value = data.config;
                showMessage('config-message', 'Configuration loaded successfully', 'success');
            } catch (error) {
                showMessage('config-message', 'Failed to load configuration', 'error');
            }
        }

        // Save configuration
        async function saveConfig() {
            const config = document.getElementById('config-editor').value;
            try {
                const response = await fetch('/api/config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ config }),
                });
                
                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.detail || 'Failed to save config');
                }
                
                showMessage('config-message', 'Configuration saved successfully! It will be reloaded automatically.', 'success');
            } catch (error) {
                showMessage('config-message', error.message, 'error');
            }
        }

        // Trigger manual sync
        async function triggerSync(event) {
            if (event) {
                event.preventDefault();
                event.stopPropagation();
            }
            
            const btn = document.getElementById('sync-now-btn');
            if (btn.disabled) return;
            
            btn.disabled = true;
            btn.textContent = '⏳ Syncing...';
            
            try {
                const response = await fetch('/api/sync/trigger', { method: 'POST' });
                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.detail || 'Sync failed');
                }
                
                // Poll for completion
                const checkInterval = setInterval(async () => {
                    await updateStatus();
                    const statusResponse = await fetch('/api/status');
                    const statusData = await statusResponse.json();
                    if (!statusData.sync_in_progress) {
                        clearInterval(checkInterval);
                    }
                }, 1000);
            } catch (error) {
                console.error('Failed to trigger sync:', error);
                await updateStatus(); // Restore button state
            }
        }

        // Show message
        function showMessage(elementId, message, type) {
            const msgEl = document.getElementById(elementId);
            msgEl.textContent = message;
            msgEl.className = `message ${type} show`;
            setTimeout(() => msgEl.classList.remove('show'), 5000);
        }

        // Initialize on page load
        window.addEventListener('DOMContentLoaded', () => {
            updateStatus();
            loadConfig();
            setInterval(updateStatus, 30000); // Auto-refresh every 30 seconds
        });
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)


@app.get("/api/status")
async def get_status() -> SyncStatus:
    """Get current sync status"""
    status_dict = sync_status.copy()
    status_dict["sync_in_progress"] = is_sync_running()
    return SyncStatus(**status_dict)


@app.get("/api/config")
async def get_config():
    """Get current configuration"""
    try:
        config_path = _get_config_path()
        if not config_path.exists():
            raise HTTPException(status_code=404, detail="Config file not found")
        
        with open(config_path, "r") as f:
            return {"config": f.read()}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/config")
async def update_config(data: ConfigUpdate):
    """Update configuration file"""
    config_path = _get_config_path()
    backup_path = config_path.parent / "config.yaml.backup"
    
    try:
        # Validate YAML syntax
        yaml.safe_load(data.config)
        
        # Backup existing config
        if config_path.exists():
            with open(config_path, "r") as f:
                backup_content = f.read()
            with open(backup_path, "w") as f:
                f.write(backup_content)
        
        # Write new config
        with open(config_path, "w") as f:
            f.write(data.config)
        
        # Validate and reload
        try:
            reload_settings()
        except Exception as e:
            # Restore backup on validation failure
            if backup_path.exists():
                with open(backup_path, "r") as f:
                    with open(config_path, "w") as f2:
                        f2.write(f.read())
            raise HTTPException(status_code=400, detail=f"Invalid configuration: {str(e)}")
        
        return {"message": "Configuration updated successfully and reloaded"}
    except HTTPException:
        raise
    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to update config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/sync/trigger")
async def trigger_sync():
    """Trigger an immediate sync"""
    if not acquire_sync_lock():
        raise HTTPException(status_code=409, detail="Sync already in progress")
    
    try:
        settings = get_settings()
        mode = _cli_sync_mode if _cli_sync_mode else settings.sync_mode
        dry_run = _cli_dry_run if _cli_dry_run is not None else settings.dry_run
        
        def run_manual_sync():
            try:
                logger.info(f"[INFO] Manual sync started (mode: {mode})")
                update_sync_status(running=True)
                success, result = execute_sync(mode, dry_run=dry_run, settings=settings)
                
                if success and result:
                    total = result.entries_synced + result.entries_failed
                    if result.success:
                        result_msg = f"{result.entries_synced}/{total} synced, 0 failed (Manual)"
                        logger.info(f"[INFO] Manual sync completed: {result_msg}")
                    elif result.entries_synced > 0:
                        result_msg = f"{result.entries_synced}/{total} synced, {result.entries_failed} failed (Manual)"
                        logger.warning(f"[WARNING] Manual sync completed: {result_msg}")
                    else:
                        result_msg = f"0/{total} synced, {result.entries_failed} failed (Manual)"
                        logger.error(f"[ERROR] Manual sync failed: {result_msg}")
                    
                    update_sync_status(
                        last_sync=time.strftime('%Y-%m-%d %H:%M:%S %Z'),
                        last_result=result_msg
                    )
                else:
                    logger.error("[ERROR] Manual sync failed: Could not execute sync")
                    update_sync_status(
                        last_sync=time.strftime('%Y-%m-%d %H:%M:%S %Z'),
                        last_result="Failed (Manual)"
                    )
            except Exception as e:
                logger.error(f"[ERROR] Manual sync failed: {e}")
                update_sync_status(
                    last_sync=time.strftime('%Y-%m-%d %H:%M:%S %Z'),
                    last_result=f"Error: {str(e)} (Manual)"
                )
            finally:
                _sync_lock.release()
        
        threading.Thread(target=run_manual_sync, daemon=True).start()
        return {"message": "Sync triggered successfully"}
    except Exception as e:
        _sync_lock.release()
        logger.error(f"Failed to trigger sync: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def update_sync_status(running: bool = None, last_sync: str = None, 
                       next_sync: str = None, last_result: str = None):
    """Update the global sync status (called from CLI)"""
    if running is not None:
        sync_status["running"] = running
    if last_sync:
        sync_status["last_sync"] = last_sync
    if next_sync:
        sync_status["next_sync"] = next_sync
    if last_result:
        sync_status["last_result"] = last_result
        sync_status["total_syncs"] += 1


def set_cli_sync_params(mode: str, dry_run: bool):
    """Set the sync mode and dry_run from CLI (called when web UI starts)"""
    global _cli_sync_mode, _cli_dry_run
    _cli_sync_mode = mode
    _cli_dry_run = dry_run


def is_sync_running() -> bool:
    """Check if any sync (scheduled or manual) is currently running"""
    return _sync_lock.locked()


def acquire_sync_lock() -> bool:
    """Try to acquire the sync lock. Returns True if acquired, False if already locked."""
    return _sync_lock.acquire(blocking=False)
