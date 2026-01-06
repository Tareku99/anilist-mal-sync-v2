"""AniList API client."""

import logging
from typing import Optional

from .base_client import BaseAPIClient
from .models import AnimeEntry, WatchStatus

logger = logging.getLogger(__name__)

# HTTP Status Code Constants
HTTP_OK = 200
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403


class AniListClient(BaseAPIClient):
    """Client for AniList GraphQL API."""

    BASE_URL = "https://graphql.anilist.co"

    def __init__(self, access_token: str):
        """Initialize AniList client with access token."""
        super().__init__(
            access_token=access_token,
            base_url=self.BASE_URL,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

    def _query(self, query: str, variables: Optional[dict] = None) -> dict:
        """Execute a GraphQL query."""
        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        response = self.session.post(self.base_url, json=payload)

        if response.status_code != HTTP_OK:
            self._handle_auth_error(response, "AniList")
            if response.status_code not in (HTTP_UNAUTHORIZED, HTTP_FORBIDDEN):
                logger.error(f"AniList API error: {response.status_code}")
                logger.error(f"Response: {response.text}")
        
        response.raise_for_status()

        data = response.json()
        if "errors" in data:
            logger.error(f"GraphQL errors: {data['errors']}")
            raise Exception(f"GraphQL errors: {data['errors']}")

        return data.get("data", {})

    def get_user_anime_list(self, username: Optional[str] = None) -> list[AnimeEntry]:
        """Fetch user's anime list from AniList."""
        query = """
        query ($userName: String) {
          MediaListCollection(userName: $userName, type: ANIME) {
            lists {
              entries {
                id
                status
                score(format: POINT_10_DECIMAL)
                progress
                progressVolumes
                repeat
                notes
                startedAt { year month day }
                completedAt { year month day }
                updatedAt
                media {
                  id
                  idMal
                  isFavourite
                  title { romaji english native }
                  episodes
                }
              }
            }
          }
        }
        """

        # If no username provided, get current authenticated user
        variables = {"userName": username} if username else None

        data = self._query(query, variables)
        entries = []

        for list_group in data.get("MediaListCollection", {}).get("lists", []):
            for entry in list_group.get("entries", []):
                entries.append(self._parse_entry(entry))

        logger.info(f"Fetched {len(entries)} anime entries from AniList")
        return entries

    def search_anime(self, title: str, limit: int = 5) -> list[dict]:
        """Search AniList anime by title to find IDs."""
        query = """
        query ($search: String, $limit: Int) {
            Page(perPage: $limit) {
                media(search: $search, type: ANIME) {
                    id
                    idMal
                    title { romaji english native }
                }
            }
        }
        """

        variables = {"search": title, "limit": limit}
        try:
            data = self._query(query, variables)
            return data.get("Page", {}).get("media", [])
        except Exception as e:
            logger.error(f"AniList search failed for '{title}': {e}")
            return []

    def _parse_entry(self, entry: dict) -> AnimeEntry:
        """Parse AniList entry to common model."""
        media = entry.get("media", {})
        title_data = media.get("title", {})
        title = title_data.get("romaji") or title_data.get("english") or title_data.get("native")

        # Map AniList status to common status
        status_map = {
            "CURRENT": WatchStatus.WATCHING,
            "COMPLETED": WatchStatus.COMPLETED,
            "PAUSED": WatchStatus.ON_HOLD,
            "DROPPED": WatchStatus.DROPPED,
            "PLANNING": WatchStatus.PLAN_TO_WATCH,
        }
        
        # Parse updated_at timestamp (Unix timestamp from AniList)
        updated_at = None
        if entry.get("updatedAt"):
            from datetime import datetime, timezone
            updated_at = datetime.fromtimestamp(entry["updatedAt"], tz=timezone.utc)

        return AnimeEntry(
            anilist_id=media.get("id"),
            mal_id=media.get("idMal"),
            title=title,
            status=status_map.get(entry.get("status"), WatchStatus.WATCHING),
            score=entry.get("score"),
            episodes_watched=entry.get("progress", 0),
            total_episodes=media.get("episodes"),
            notes=entry.get("notes"),
            rewatched=entry.get("repeat", 0),
            is_favorite=media.get("isFavourite", False),
            updated_at=updated_at,
        )

    def update_anime(self, entry: AnimeEntry) -> bool:
        """Update an anime entry on AniList."""
        if not entry.anilist_id:
            logger.warning(f"Cannot update AniList entry without anilist_id: {entry.title}")
            return False

        # Reverse map status
        status_map = {
            WatchStatus.WATCHING: "CURRENT",
            WatchStatus.COMPLETED: "COMPLETED",
            WatchStatus.ON_HOLD: "PAUSED",
            WatchStatus.DROPPED: "DROPPED",
            WatchStatus.PLAN_TO_WATCH: "PLANNING",
        }

        mutation = """
        mutation ($mediaId: Int, $status: MediaListStatus, $score: Float, $progress: Int, $repeat: Int, $notes: String) {
          SaveMediaListEntry(mediaId: $mediaId, status: $status, score: $score, progress: $progress, repeat: $repeat, notes: $notes) {
            id
          }
        }
        """

        variables = {
            "mediaId": entry.anilist_id,
            "status": status_map.get(entry.status),
            "score": entry.score,
            "progress": entry.episodes_watched,
            "repeat": entry.rewatched,
            "notes": entry.notes,
        }

        try:
            self._query(mutation, variables)
            logger.info(f"Updated AniList entry: {entry.title}")
            return True
        except Exception as e:
            logger.error(f"Failed to update AniList entry {entry.title}: {e}")
            return False
