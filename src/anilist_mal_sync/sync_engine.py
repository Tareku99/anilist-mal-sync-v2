"""Core sync engine for anime list synchronization."""

import logging
from typing import Literal

from .anilist_client import AniListClient
from .config import get_settings
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

    @staticmethod
    def _normalize_score_for_mal(score: float | None) -> int | None:
        """Normalize score to MAL's 0-10 integer scale."""
        if score is None:
            return None
        normalized = score
        if normalized > 10:
            normalized = normalized / 10.0
        return int(round(normalized))

    @staticmethod
    def _safe_title(title: str) -> str:
        """Return a console-safe title string (avoid encoding errors on Windows)."""
        if not title:
            return ""
        return title.encode("ascii", "replace").decode("ascii")

    def _needs_update(
        self, 
        source_entry: AnimeEntry, 
        target_entry: AnimeEntry | None, 
        score_sync_mode: str
    ) -> bool:
        """Check if target entry needs update based on source entry."""
        if target_entry is None:
            logger.debug("    -> Target entry is None, will update")
            return True

        # Compare fields we actually send to the target
        if source_entry.status != target_entry.status:
            logger.debug(f"  Status differs: {source_entry.status} != {target_entry.status}")
            return True
        if source_entry.episodes_watched != target_entry.episodes_watched:
            logger.debug(f"  Episodes differ: {source_entry.episodes_watched} != {target_entry.episodes_watched}")
            return True
        if source_entry.rewatched != target_entry.rewatched:
            logger.debug(f"  Rewatched differs: {source_entry.rewatched} != {target_entry.rewatched}")
            return True
        if (source_entry.notes or "") != (target_entry.notes or ""):
            logger.debug(f"  Notes differ: '{source_entry.notes}' != '{target_entry.notes}'")
            return True

        if score_sync_mode == "auto":
            source_score = self._normalize_score_for_mal(source_entry.score)
            target_score = self._normalize_score_for_mal(target_entry.score)
            if source_score != target_score:
                logger.debug(f"  Score differs: {source_score} != {target_score}")
                return True

        return False

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
        summary = {
            "attempted": 0,
            "updated": 0,
            "skipped_missing_id": 0,
            "skipped_not_found": 0,
            "skipped_unchanged": 0,
            "failed": 0,
        }

        settings = get_settings()

        # Fetch source list (use configured username for AniList)
        if source == "anilist":
            username = settings.anilist_username or None
            source_entries = self.anilist.get_user_anime_list(username)
            target_client = self.mal
            target_entries = {e.mal_id: e for e in target_client.get_user_anime_list()}
        else:
            source_entries = self.mal.get_user_anime_list()
            target_client = self.anilist
            # For MAL -> AniList, fetch target list to build lookup dict for change detection
            username = settings.anilist_username or None
            target_entries = {e.anilist_id: e for e in target_client.get_user_anime_list(username) if e.anilist_id}

        # Update target for each entry
        for entry in source_entries:
            try:
                summary["attempted"] += 1

                # If syncing AniList -> MAL and MAL ID is missing, skip with a clear log
                if source == "anilist" and not entry.mal_id:
                    summary["skipped_missing_id"] += 1
                    logger.warning(f"Skipping AniList entry without MAL ID: {self._safe_title(entry.title)}")
                    continue

                # Check if update is needed for AniList -> MAL
                if target == "mal" and entry.mal_id:
                    target_entry = target_entries.get(entry.mal_id)
                    score_mode = settings.score_sync_mode if source == "anilist" else "disabled"
                    target_id = entry.mal_id
                    
                    logger.debug(f"Checking if update needed for {self._safe_title(entry.title)} (MAL ID {target_id})")
                    if target_entry is None:
                        logger.debug(f"  -> MAL entry not found in dict, will update")
                    elif not self._needs_update(entry, target_entry, score_mode):
                        summary["skipped_unchanged"] += 1
                        logger.info(f"No changes for {self._safe_title(entry.title)}, skipping")
                        continue
                    else:
                        logger.debug(f"  -> Will update (changes detected)")

                # If syncing MAL -> AniList, resolve AniList ID when missing
                if target == "anilist" and not entry.anilist_id:
                    if isinstance(self.anilist, AniListClient):
                        matches = self.anilist.search_anime(entry.title, limit=3)
                        match_id = None
                        for m in matches:
                            # Prefer exact case-insensitive title match
                            titles = [m.get("title", {}).get(k) for k in ["romaji", "english", "native"]]
                            if any(t and t.lower() == entry.title.lower() for t in titles):
                                match_id = m.get("id")
                                break
                        if not match_id and matches:
                            match_id = matches[0].get("id")

                        if match_id:
                            entry.anilist_id = match_id
                        else:
                            summary["skipped_not_found"] += 1
                            logger.warning(f"No AniList match found for MAL entry: {self._safe_title(entry.title)}")
                            continue
                
                # Check if update is needed for MAL -> AniList (after resolving ID)
                elif target == "anilist" and entry.anilist_id:
                    target_entry = target_entries.get(entry.anilist_id)
                    score_mode = "auto"  # AniList accepts 100-point scores, so we can sync them
                    target_id = entry.anilist_id
                    
                    logger.debug(f"Checking if update needed for {self._safe_title(entry.title)} (AniList ID {target_id})")
                    if target_entry is None:
                        logger.debug(f"  -> AniList entry not found in dict, will update")
                    elif not self._needs_update(entry, target_entry, score_mode):
                        summary["skipped_unchanged"] += 1
                        logger.info(f"No changes for {self._safe_title(entry.title)}, skipping")
                        continue
                    else:
                        logger.debug(f"  -> Will update (changes detected)")

                if self.dry_run:
                    logger.info(f"[DRY RUN] Would sync: {self._safe_title(entry.title)}")
                    result.entries_synced += 1
                    summary["updated"] += 1
                else:
                    if target_client.update_anime(entry):
                        result.entries_synced += 1
                        summary["updated"] += 1
                    else:
                        result.entries_failed += 1
                        summary["failed"] += 1
                        result.errors.append(f"Failed to sync: {entry.title}")
            except Exception as e:
                logger.error(f"Error syncing {self._safe_title(entry.title)}: {e}")
                result.entries_failed += 1
                summary["failed"] += 1
                result.errors.append(f"{entry.title}: {str(e)}")

        result.success = result.entries_failed == 0
        logger.info(
            f"Summary: attempted={summary['attempted']}, updated={summary['updated']}, "
            f"skipped_missing_id={summary['skipped_missing_id']}, "
            f"skipped_not_found={summary['skipped_not_found']}, "
            f"skipped_unchanged={summary['skipped_unchanged']}, failed={summary['failed']}"
        )
        return result

    def _sync_bidirectional(self) -> SyncResult:
        """Sync both ways with conflict resolution (latest update wins)."""
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
                    if self._resolve_conflict(anilist_entry, mal_entry):
                        result.entries_synced += 1
                    else:
                        result.entries_failed += 1
                        result.errors.append(f"MAL ID {mal_id}: Failed to sync conflict")

            except Exception as e:
                logger.error(f"Error in bidirectional sync for MAL ID {mal_id}: {e}")
                result.entries_failed += 1
                result.errors.append(f"MAL ID {mal_id}: {str(e)}")

        result.success = result.entries_failed == 0
        return result

    def _resolve_conflict(self, anilist_entry: AnimeEntry, mal_entry: AnimeEntry) -> bool:
        """Resolve conflicts between AniList and MAL entries (latest update wins).
        
        Returns:
            bool: True if sync was successful or no sync needed, False if sync failed.
        """
        # Use timestamps to determine which entry is newer
        if anilist_entry.updated_at and mal_entry.updated_at:
            if anilist_entry.updated_at > mal_entry.updated_at:
                logger.info(
                    f"AniList has newer update for {anilist_entry.title} "
                    f"(AL: {anilist_entry.updated_at}, MAL: {mal_entry.updated_at}), syncing to MAL"
                )
                if self.dry_run:
                    return True
                return self.mal.update_anime(anilist_entry)
            elif mal_entry.updated_at > anilist_entry.updated_at:
                logger.info(
                    f"MAL has newer update for {mal_entry.title} "
                    f"(MAL: {mal_entry.updated_at}, AL: {anilist_entry.updated_at}), syncing to AniList"
                )
                if self.dry_run:
                    return True
                # Copy AniList ID from the matched entry to the MAL entry
                mal_entry.anilist_id = anilist_entry.anilist_id
                return self.anilist.update_anime(mal_entry)
            else:
                logger.debug(f"Entries in sync for {anilist_entry.title}, same update time")
                return True
        else:
            # Fallback to episode count if timestamps missing
            logger.warning(f"Missing timestamps for {anilist_entry.title}, using episode count fallback")
            if anilist_entry.episodes_watched > mal_entry.episodes_watched:
                logger.info(f"AniList has more progress for {anilist_entry.title}, syncing to MAL")
                if self.dry_run:
                    return True
                return self.mal.update_anime(anilist_entry)
            elif mal_entry.episodes_watched > anilist_entry.episodes_watched:
                logger.info(f"MAL has more progress for {mal_entry.title}, syncing to AniList")
                if self.dry_run:
                    return True
                # Copy AniList ID from the matched entry to the MAL entry
                mal_entry.anilist_id = anilist_entry.anilist_id
                return self.anilist.update_anime(mal_entry)
            else:
                # Episodes are the same, no sync needed
                return True
