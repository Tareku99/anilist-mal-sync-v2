"""Data models for anime entries."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class WatchStatus(str, Enum):
    """Anime watch status."""

    WATCHING = "watching"
    COMPLETED = "completed"
    ON_HOLD = "on_hold"
    DROPPED = "dropped"
    PLAN_TO_WATCH = "plan_to_watch"


class AnimeEntry(BaseModel):
    """Common anime entry model."""

    # Identifiers
    anilist_id: Optional[int] = None
    mal_id: Optional[int] = None
    title: str

    # Watch data
    status: WatchStatus
    score: Optional[float] = Field(None, ge=0, le=10)
    episodes_watched: int = Field(default=0, ge=0)
    total_episodes: Optional[int] = None

    # Dates
    start_date: Optional[datetime] = None
    finish_date: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Additional metadata
    notes: Optional[str] = None
    rewatched: int = Field(default=0, ge=0)


class SyncResult(BaseModel):
    """Result of a sync operation."""

    success: bool
    entries_synced: int = 0
    entries_failed: int = 0
    errors: list[str] = Field(default_factory=list)
    dry_run: bool = False
