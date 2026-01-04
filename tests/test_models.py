"""Unit tests for data models."""

import pytest
from anilist_mal_sync.models import AnimeEntry, WatchStatus


def test_anime_entry_creation():
    """Test creating an anime entry."""
    entry = AnimeEntry(
        anilist_id=1,
        mal_id=1,
        title="Test Anime",
        status=WatchStatus.WATCHING,
        episodes_watched=5,
    )

    assert entry.anilist_id == 1
    assert entry.mal_id == 1
    assert entry.title == "Test Anime"
    assert entry.status == WatchStatus.WATCHING
    assert entry.episodes_watched == 5


def test_score_validation():
    """Test score validation (allows AniList 100-point scale)."""
    # Valid 10-point score
    entry = AnimeEntry(
        title="Test",
        status=WatchStatus.WATCHING,
        score=8.5,
    )
    assert entry.score == 8.5
    
    # Valid 100-point score (AniList format)
    entry_100 = AnimeEntry(
        title="Test",
        status=WatchStatus.WATCHING,
        score=85.0,
    )
    assert entry_100.score == 85.0

    # Invalid negative score should raise validation error
    with pytest.raises(Exception):
        AnimeEntry(
            title="Test",
            status=WatchStatus.WATCHING,
            score=-1,
        )
