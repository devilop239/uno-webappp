# -*- coding: utf-8 -*-
"""
Bridges a mini-game result into the Uno bot's own shared points ledger
(the `player_stats` collection), so mini-game points count toward the same
total/weekly/monthly/season points and show up on Uno's existing
/leaderboard, /weeklylb, /monthlylb, /seasonlb — with zero changes to any
of those existing Uno files.

This is shared infrastructure, not owned by any one mini-game — Wild Word
and RPS both call the same `credit_shared_points()`. It intentionally
mirrors services/match_service.py's `_apply_points_bundle` bucket-rollover
logic (same week/month/season reset rules), so the numbers behave
identically to a normal Uno win as far as those commands are concerned.
It's read-only with respect to Uno's own code — only `db.player_stats`
gets written to, using the exact same field shape Uno itself already
writes.

Unlike Wild Word (wins only, always positive), RPS can also *deduct*
points (a "cold" loss). `credit_shared_points()` accepts negative amounts
for that reason, and each bucket (total/weekly/monthly/season) is floored
at 0 — an unlucky streak of losses should never push a player's displayed
points negative on a leaderboard.
"""

import logging

from config import SEASON_ID
from db.mongo_client import default_player_stats_doc, fetch_player_stats_document, get_database
from services.stats_policy import is_leaderboard_banned
from services.time_buckets import month_bucket, utc_now, week_bucket

logger = logging.getLogger(__name__)


def credit_shared_points(user_id: int, amount: int, *, reason: str = "minigame") -> None:
    """
    Adds `amount` (positive OR negative) to a player's shared Uno points
    (total/weekly/monthly/season), respecting the same leaderboard-ban flag
    and bucket-rollover rules Uno's own match scoring uses. Each bucket is
    floored at 0. No-op if Mongo isn't configured, amount==0, or the player
    is leaderboard-banned (same as a normal Uno match would respect).

    `reason` is only used for logging (e.g. "wildword_win", "rps_win",
    "rps_cold_loss") — it has no effect on behavior.
    """
    if amount == 0:
        return
    if is_leaderboard_banned(user_id):
        logger.info("%s: user %s is leaderboard-banned, skipping points change", reason, user_id)
        return

    db = get_database()
    if db is None:
        logger.warning("%s: MongoDB not configured, skipping points change for user %s", reason, user_id)
        return

    try:
        db.player_stats.update_one(
            {"_id": user_id},
            {"$setOnInsert": {**default_player_stats_doc(user_id), "created_at": utc_now().isoformat()}},
            upsert=True,
        )
        cur = fetch_player_stats_document(db, user_id) or {}

        wb = week_bucket()
        mb = month_bucket()
        cur_week = (cur.get("week_bucket") or "").strip()
        cur_month = (cur.get("month_bucket") or "").strip()
        cur_season = (cur.get("season_id") or "").strip()

        # A bucket that just rolled over starts fresh from 0 before this
        # delta is applied, same as Wild Word's original logic — the only
        # change here is flooring every result at 0 afterward.
        base_weekly = 0 if (cur_week and cur_week != wb) else int(cur.get("weekly_points") or 0)
        base_monthly = 0 if (cur_month and cur_month != mb) else int(cur.get("monthly_points") or 0)
        base_season = 0 if (cur_season and cur_season != SEASON_ID) else int(cur.get("season_points") or 0)
        base_total = int(cur.get("total_points") or 0)

        new_total = max(0, base_total + amount)
        new_weekly = max(0, base_weekly + amount)
        new_monthly = max(0, base_monthly + amount)
        new_season = max(0, base_season + amount)

        db.player_stats.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "total_points": new_total,
                    "weekly_points": new_weekly,
                    "monthly_points": new_monthly,
                    "season_points": new_season,
                    "week_bucket": wb,
                    "month_bucket": mb,
                    "season_id": SEASON_ID,
                    "updated_at": utc_now().isoformat(),
                }
            },
        )
        logger.info("%s: applied %+d points to user %s (total now %d)", reason, amount, user_id, new_total)
    except Exception:
        logger.exception("%s: failed to apply shared points user_id=%s amount=%s", reason, user_id, amount)
