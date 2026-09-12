# -*- coding: utf-8 -*-
"""Leaderboard queries (all-time, week, month, season)."""

import html
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from config import SEASON_ID
from internationalization import _
from db.mongo_client import get_database
from services.time_buckets import month_bucket, week_bucket

logger = logging.getLogger(__name__)

_PUBLIC_CACHE: Dict[Tuple[str, int], Tuple[float, List[Dict[str, Any]]]] = {}
_PUBLIC_CACHE_TTL = 45.0


def _display_name(row: Dict[str, Any]) -> str:
    d = (row.get("display_name") or "").strip()
    if d:
        return d
    u = (row.get("username") or "").strip()
    if u:
        return "@" + u
    uid = row.get("user_id", row.get("_id", "?"))
    return "Player %s" % uid


def _leaderboard_link_label(row: Dict[str, Any]) -> str:
    """Visible name for leaderboard (no raw numeric id when avoidable)."""
    d = (row.get("display_name") or "").strip()
    if d:
        return d
    u = (row.get("username") or "").strip()
    if u:
        return "@" + u
    return _("Player")


def _leaderboard_name_html(row: Dict[str, Any]) -> str:
    """Clickable profile link; falls back to escaped plain text if user id missing."""
    uid = row.get("user_id", row.get("_id"))
    try:
        uid_int = int(uid)
    except (TypeError, ValueError):
        return html.escape(_display_name(row))
    if uid_int <= 0:
        return html.escape(_display_name(row))
    label = _leaderboard_link_label(row)
    return '<a href="tg://user?id=%d">%s</a>' % (uid_int, html.escape(label))


def _normalize_row(doc: Dict[str, Any]) -> Dict[str, Any]:
    row = dict(doc)
    row.setdefault("user_id", row.get("_id"))
    return row


def _top_by(
    order_column: str,
    extra_filter: Optional[Tuple[str, str]] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    db = get_database()
    if db is None:
        return []
    try:
        filt: Dict[str, Any] = {"stats_banned": {"$ne": True}}
        if extra_filter:
            filt[extra_filter[0]] = extra_filter[1]
        cur = (
            db.player_stats.find(filt)
            .sort([(order_column, -1), ("_id", 1)])
            .limit(limit)
        )
        return [_normalize_row(d) for d in cur]
    except Exception:
        logger.exception("leaderboard query failed column=%s", order_column)
        return []


def top_total(limit: int = 10) -> List[Dict[str, Any]]:
    return _top_by("total_points", limit=limit)


def get_global_leaderboard(category: str = "points", period: str = "all", limit: int = 20) -> List[Dict[str, Any]]:
    """Return a bounded public points board with a short process-local cache."""
    limit = max(1, min(int(limit), 50))
    period = {"all": "all", "week": "week", "month": "month"}.get(period, "all")
    cache_key = (period, limit)
    cached = _PUBLIC_CACHE.get(cache_key)
    if cached and time.monotonic() - cached[0] < _PUBLIC_CACHE_TTL:
        return [dict(row) for row in cached[1]]

    if period == "week":
        rows = top_weekly(limit)
        points_key = "weekly_points"
    elif period == "month":
        rows = top_monthly(limit)
        points_key = "monthly_points"
    else:
        rows = top_total(limit)
        points_key = "total_points"

    public_rows = []
    for index, row in enumerate(rows, 1):
        public_rows.append({
            "rank": index,
            "user_id": row.get("user_id", row.get("_id")),
            "name": _display_name(row),
            "points": int(row.get(points_key) or 0),
        })
    _PUBLIC_CACHE[cache_key] = (time.monotonic(), public_rows)
    return [dict(row) for row in public_rows]


def invalidate_public_leaderboard_cache() -> None:
    _PUBLIC_CACHE.clear()


def top_global_points(limit: int = 10) -> List[Dict[str, Any]]:
    """Global points board across all users (all-time total_points)."""
    return top_total(limit=limit)


def top_weekly(limit: int = 10) -> List[Dict[str, Any]]:
    wb = week_bucket()
    return _top_by("weekly_points", ("week_bucket", wb), limit=limit)


def top_monthly(limit: int = 10) -> List[Dict[str, Any]]:
    mb = month_bucket()
    return _top_by("monthly_points", ("month_bucket", mb), limit=limit)


def top_season(limit: int = 10) -> List[Dict[str, Any]]:
    return _top_by("season_points", ("season_id", SEASON_ID), limit=limit)


def top_chat_points(chat_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Chat-scoped points board by summing `matches.points_awarded` for this chat.
    Uses persisted match results so it's stable across restarts.
    """
    db = get_database()
    if db is None:
        return []
    try:
        cid = int(chat_id)
    except (TypeError, ValueError):
        return []

    try:
        pipeline = [
            {"$match": {"chat_id": cid}},
            {"$project": {"aw": {"$objectToArray": {"$ifNull": ["$points_awarded", {}]}}}},
            {"$unwind": "$aw"},
            {"$group": {"_id": "$aw.k", "total_points": {"$sum": "$aw.v"}}},
            {"$sort": {"total_points": -1, "_id": 1}},
            {"$limit": int(limit)},
        ]
        agg = list(db.matches.aggregate(pipeline))
        if not agg:
            return []

        user_ids: List[int] = []
        for row in agg:
            try:
                user_ids.append(int(row.get("_id")))
            except (TypeError, ValueError):
                continue

        stats_profiles: Dict[int, Dict[str, Any]] = {}
        if user_ids:
            for d in db.player_stats.find(
                {"_id": {"$in": user_ids}},
                projection=["_id", "user_id", "username", "display_name"],
            ):
                uid = int(d.get("_id"))
                stats_profiles[uid] = d

        user_profiles: Dict[int, Dict[str, Any]] = {}
        missing = [uid for uid in user_ids if uid not in stats_profiles]
        if missing:
            for d in db.users.find(
                {"_id": {"$in": missing}},
                projection=["_id", "username", "display_name"],
            ):
                uid = int(d.get("_id"))
                user_profiles[uid] = d

        out: List[Dict[str, Any]] = []
        banned_ids = set()
        if user_ids:
            for row in db.player_stats.find(
                {"_id": {"$in": user_ids}, "stats_banned": True},
                projection=["_id"],
            ):
                try:
                    banned_ids.add(int(row.get("_id")))
                except (TypeError, ValueError):
                    continue
        for row in agg:
            try:
                uid = int(row.get("_id"))
            except (TypeError, ValueError):
                continue
            if uid in banned_ids:
                continue
            profile = stats_profiles.get(uid) or user_profiles.get(uid) or {}
            out.append(
                {
                    "user_id": uid,
                    "username": profile.get("username", ""),
                    "display_name": profile.get("display_name", ""),
                    "total_points": int(row.get("total_points") or 0),
                }
            )
        return out
    except Exception:
        logger.exception("chat leaderboard query failed chat_id=%s", cid)
        return []


def rank_for_user(user_id: int, scope: str) -> Optional[int]:
    """1-based rank in scope: total | weekly | monthly | season."""
    db = get_database()
    if db is None:
        return None
    col = {
        "total": "total_points",
        "weekly": "weekly_points",
        "monthly": "monthly_points",
        "season": "season_points",
    }.get(scope, "total_points")
    try:
        filt: Dict[str, Any] = {"stats_banned": {"$ne": True}}
        if scope == "weekly":
            filt["week_bucket"] = week_bucket()
        elif scope == "monthly":
            filt["month_bucket"] = month_bucket()
        elif scope == "season":
            filt["season_id"] = SEASON_ID
        
        # Use aggregation for efficient rank calculation
        pipeline = [
            {"$match": filt},
            {"$sort": {col: -1, "_id": 1}},
            {"$group": {"_id": None, "user_ids": {"$push": "$_id"}}},
            {"$project": {"rank": {"$indexOfArray": ["$user_ids", user_id]}}},
        ]
        
        result = list(db.player_stats.aggregate(pipeline))
        if result and result[0].get("rank") is not None:
            return result[0]["rank"] + 1  # 1-based rank
        return None
    except Exception:
        logger.exception("rank_for_user failed")
        return None


def format_leaderboard_rows(rows: List[Dict[str, Any]], points_key: str) -> str:
    lines = []
    medals = ("🥇", "🥈", "🥉")
    for i, row in enumerate(rows):
        medal = medals[i] if i < 3 else "▫️"
        pts = int(row.get(points_key) or 0)
        name = _leaderboard_name_html(row)
        lines.append("%s <b>%d.</b> %s — <code>%d</code>" % (medal, i + 1, name, pts))
    return "\n".join(lines) if lines else "—"
