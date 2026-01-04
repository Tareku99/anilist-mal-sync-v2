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
    """Test score validation (0-10 range)."""
    # Valid score
    entry = AnimeEntry(
        title="Test",
        status=WatchStatus.WATCHING,
        score=8.5,
    )
    assert entry.score == 8.5

    # Invalid score should raise validation error
    with pytest.raises(Exception):
        AnimeEntry(
            title="Test",
            status=WatchStatus.WATCHING,
            score=11.0,  # Out of range
        )
