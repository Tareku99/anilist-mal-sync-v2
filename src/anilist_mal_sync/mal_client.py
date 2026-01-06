"""MyAnimeList API client."""

import logging
from typing import Optional

from .base_client import BaseAPIClient
from .models import AnimeEntry, WatchStatus

logger = logging.getLogger(__name__)


class MALClient(BaseAPIClient):
    """Client for MyAnimeList API v2."""

    BASE_URL = "https://api.myanimelist.net/v2"

    def __init__(self, access_token: str):
        """Initialize MAL client with access token."""
        super().__init__(access_token=access_token, base_url=self.BASE_URL)

    def get_user_anime_list(self, username: str = "@me") -> list[AnimeEntry]:
        """Fetch user's anime list from MyAnimeList."""
        entries = []
        url = f"{self.base_url}/users/{username}/animelist"
        params = {
              "fields": "list_status{updated_at},num_episodes,alternative_titles",
            "limit": 1000,
        }

        while url:
            response = self.session.get(url, params=params)
            self._handle_auth_error(response, "MyAnimeList")
            response.raise_for_status()
            data = response.json()

            for item in data.get("data", []):
                entries.append(self._parse_entry(item))

            # Pagination
            url = data.get("paging", {}).get("next")
            params = {}  # Next URL already contains params

        logger.info(f"Fetched {len(entries)} anime entries from MyAnimeList")
        return entries

    def _parse_entry(self, item: dict) -> AnimeEntry:
        """Parse MAL entry to common model."""
        node = item.get("node", {})
        list_status = item.get("list_status", {})

        # Map MAL status to common status
        status_map = {
            "watching": WatchStatus.WATCHING,
            "completed": WatchStatus.COMPLETED,
            "on_hold": WatchStatus.ON_HOLD,
            "dropped": WatchStatus.DROPPED,
            "plan_to_watch": WatchStatus.PLAN_TO_WATCH,
        }

        # MAL uses 0-10 integer scores, convert to float
        score = list_status.get("score")
        if score is not None:
            score = float(score)
        
            # Parse updated_at timestamp
            updated_at = None
            if list_status.get("updated_at"):
                from datetime import datetime
                updated_at = datetime.fromisoformat(list_status["updated_at"].replace("Z", "+00:00"))

        return AnimeEntry(
            mal_id=node.get("id"),
            title=node.get("title"),
            status=status_map.get(list_status.get("status"), WatchStatus.WATCHING),
            score=score,
            episodes_watched=list_status.get("num_episodes_watched", 0),
            total_episodes=node.get("num_episodes"),
            notes=list_status.get("comments"),
            rewatched=list_status.get("num_times_rewatched", 0),
            is_favorite=list_status.get("is_favoriting", False),
            updated_at=updated_at,
        )

    def update_anime(self, entry: AnimeEntry) -> bool:
        """Update an anime entry on MyAnimeList."""
        from .config import get_settings
        
        if not entry.mal_id:
            logger.warning(f"Cannot update MAL entry without mal_id: {entry.title}")
            return False

        # Reverse map status
        status_map = {
            WatchStatus.WATCHING: "watching",
            WatchStatus.COMPLETED: "completed",
            WatchStatus.ON_HOLD: "on_hold",
            WatchStatus.DROPPED: "dropped",
            WatchStatus.PLAN_TO_WATCH: "plan_to_watch",
        }

        url = f"{self.base_url}/anime/{entry.mal_id}/my_list_status"
        data = {
            "status": status_map.get(entry.status),
            "num_watched_episodes": entry.episodes_watched,
        }

        # Handle score syncing based on configuration
        settings = get_settings()
        if entry.score is not None and settings.score_sync_mode == "auto":
            # Normalize score: AniList can use 100-point scale, MAL only accepts 0-10
            normalized_score = entry.score
            if normalized_score > 10:
                normalized_score = normalized_score / 10.0
            data["score"] = int(round(normalized_score))  # MAL expects 0-10 integer
        # If score_sync_mode == "disabled", skip score field entirely

        if entry.notes:
            data["comments"] = entry.notes
        
        if entry.rewatched > 0:
            data["num_times_rewatched"] = entry.rewatched

        try:
            response = self.session.patch(url, data=data)
            self._handle_auth_error(response, "MyAnimeList")
            response.raise_for_status()
            logger.info(f"Updated MAL entry: {entry.title}")
            return True
        except Exception as e:
            logger.error(f"Failed to update MAL entry {entry.title}: {e}")
            return False

    def search_anime(self, title: str, limit: int = 5) -> list[dict]:
        """Search for anime by title to find MAL ID."""
        url = f"{self.base_url}/anime"
        params = {"q": title, "limit": limit}

        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response.json().get("data", [])
        except Exception as e:
            logger.error(f"Failed to search MAL for '{title}': {e}")
            return []
