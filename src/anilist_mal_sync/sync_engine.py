"""Core sync engine for anime list synchronization."""

import logging
from typing import Literal

from .anilist_client import AniListClient
from .mal_client import MALClient
from .models import AnimeEntry, SyncResult

logger = logging.getLogger(__name__)


class SyncEngine:
    """Engine for synchronizing anime lists between AniList and MyAnimeList."""

    def __init__(
        self,
        anilist_client: AniListClient,
        mal_client: MALClient,
        dry_run: bool = False,
    ):
        """Initialize sync engine with API clients."""
        self.anilist = anilist_client
        self.mal = mal_client
        self.dry_run = dry_run

    def sync(
        self, mode: Literal["anilist-to-mal", "mal-to-anilist", "bidirectional"]
    ) -> SyncResult:
        """Perform sync based on selected mode."""
        logger.info(f"Starting sync with mode: {mode} (dry_run={self.dry_run})")

        if mode == "anilist-to-mal":
            return self._sync_one_way(source="anilist", target="mal")
        elif mode == "mal-to-anilist":
            return self._sync_one_way(source="mal", target="anilist")
        elif mode == "bidirectional":
            return self._sync_bidirectional()
        else:
            raise ValueError(f"Unknown sync mode: {mode}")

    def _sync_one_way(self, source: str, target: str) -> SyncResult:
        """Sync from source to target (one-way)."""
        result = SyncResult(success=True, dry_run=self.dry_run)

        # Fetch source list (use configured username for AniList)
        if source == "anilist":
            from .config import get_settings
            settings = get_settings()
            username = settings.anilist_username or None
            source_entries = self.anilist.get_user_anime_list(username)
            target_client = self.mal
        else:
            source_entries = self.mal.get_user_anime_list()
            target_client = self.anilist

        # Update target for each entry
        for entry in source_entries:
            try:
                if self.dry_run:
                    logger.info(f"[DRY RUN] Would sync: {entry.title}")
                    result.entries_synced += 1
                else:
                    if target_client.update_anime(entry):
                        result.entries_synced += 1
                    else:
                        result.entries_failed += 1
                        result.errors.append(f"Failed to sync: {entry.title}")
            except Exception as e:
                logger.error(f"Error syncing {entry.title}: {e}")
                result.entries_failed += 1
                result.errors.append(f"{entry.title}: {str(e)}")

        result.success = result.entries_failed == 0
        return result

    def _sync_bidirectional(self) -> SyncResult:
        """Sync both ways with conflict resolution (latest update wins)."""
        from .config import get_settings
        
        result = SyncResult(success=True, dry_run=self.dry_run)
        settings = get_settings()
        username = settings.anilist_username or None

        # Fetch both lists
        anilist_entries = {e.mal_id: e for e in self.anilist.get_user_anime_list(username) if e.mal_id}
        mal_entries = {e.mal_id: e for e in self.mal.get_user_anime_list()}

        # Find entries to sync
        all_ids = set(anilist_entries.keys()) | set(mal_entries.keys())

        for mal_id in all_ids:
            anilist_entry = anilist_entries.get(mal_id)
            mal_entry = mal_entries.get(mal_id)

            try:
                if anilist_entry and not mal_entry:
                    # Only on AniList, add to MAL
                    if self.dry_run:
                        logger.info(f"[DRY RUN] Would add to MAL: {anilist_entry.title}")
                    else:
                        self.mal.update_anime(anilist_entry)
                    result.entries_synced += 1

                elif mal_entry and not anilist_entry:
                    # Only on MAL, add to AniList
                    if self.dry_run:
                        logger.info(f"[DRY RUN] Would add to AniList: {mal_entry.title}")
                    else:
                        self.anilist.update_anime(mal_entry)
                    result.entries_synced += 1

                elif anilist_entry and mal_entry:
                    # On both, resolve conflicts
                    self._resolve_conflict(anilist_entry, mal_entry)
                    result.entries_synced += 1

            except Exception as e:
                logger.error(f"Error in bidirectional sync for MAL ID {mal_id}: {e}")
                result.entries_failed += 1
                result.errors.append(f"MAL ID {mal_id}: {str(e)}")

        result.success = result.entries_failed == 0
        return result

    def _resolve_conflict(self, anilist_entry: AnimeEntry, mal_entry: AnimeEntry):
        """Resolve conflicts between AniList and MAL entries (latest wins)."""
        # For now, use simple rule: sync the one with more episodes watched
        # In production, you'd use updated_at timestamps

        if anilist_entry.episodes_watched > mal_entry.episodes_watched:
            logger.info(
                f"AniList has more progress for {anilist_entry.title}, syncing to MAL"
            )
            if not self.dry_run:
                self.mal.update_anime(anilist_entry)
        elif mal_entry.episodes_watched > anilist_entry.episodes_watched:
            logger.info(
                f"MAL has more progress for {mal_entry.title}, syncing to AniList"
            )
            if not self.dry_run:
                self.anilist.update_anime(mal_entry)
        else:
            logger.debug(f"No conflict for {anilist_entry.title}, entries are in sync")
