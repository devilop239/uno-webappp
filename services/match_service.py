# -*- coding: utf-8 -*-
"""Persist matches, award points, and update player_stats (idempotent per match_id)."""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from config import (
    ABANDON_PENALTY,
    LARGE_MATCH_BONUS,
    LARGE_MATCH_MIN_PLAYERS,
    MIN_VALID_PLAYERS_FOR_POINTS,
    MIN_VALID_TURNS_FOR_POINTS,
    PARTICIPATION_POINTS,
    SEASON_ID,
    SECOND_PLACE_POINTS,
    STREAK_BONUS_3,
    STREAK_BONUS_5,
    SUDDEN_DEATH_PARTICIPATION_POINTS,
    SUDDEN_DEATH_WIN_POINTS,
    THIRD_PLACE_POINTS,
    WIN_POINTS,
)
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from db.mongo_client import (
    default_player_stats_doc,
    fetch_player_stats_document,
    get_database,
)
from services import user_service
from services.stats_policy import is_leaderboard_banned
from services.time_buckets import month_bucket, utc_now, week_bucket

logger = logging.getLogger(__name__)

_END_CANCELLED = frozenset(
    {"killed_admin", "cancelled", "not_started", "unknown"}
)
_END_NO_REWARD = frozenset({"killed_admin"})
TEAM_WIN_POINTS = 80
TEAM_LOSS_POINTS = 20
TEAM_MVP_BONUS = 25


def _iso(dt) -> Optional[str]:
    if dt is None:
        return None
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    return str(dt)


def _match_status(end_reason: str, started: bool, finish_order: List[int], valid: bool) -> str:
    if not started:
        return "cancelled"
    if end_reason in _END_CANCELLED:
        return "cancelled"
    if end_reason == "abandoned_timeout":
        return "cancelled"
    # Special case: player_left_2p should be treated as completed
    if end_reason == "player_left_2p":
        return "completed"
    if not valid and not finish_order:
        return "invalid"
    # Award points for games with finish_order even if not perfectly valid
    if finish_order:
        return "completed"
    if not valid:
        return "invalid"
    return "cancelled"


def _build_placements(finish_order: List[int]) -> List[Dict[str, Any]]:
    out = []
    for i, uid in enumerate(finish_order):
        out.append({"user_id": uid, "place": i + 1})
    return out


def _emit_match_audit(
    db: Database,
    match_id: str,
    doc: Dict[str, Any],
    participants: List[int],
    end_reason: str,
) -> None:
    """Structured audit after a match row is persisted (best-effort)."""
    try:
        from loggers import schedule_audit_telegram

        fresh = db.matches.find_one(
            {"_id": match_id},
            projection=["points_awarded", "winner_id", "status"],
        )
        pa = (fresh or {}).get("points_awarded") or {}
        schedule_audit_telegram(
            "match_finalized",
            action="match_end",
            match_id=match_id,
            chat_id=doc.get("chat_id"),
            chat_title=doc.get("chat_title") or "",
            game_mode=doc.get("game_mode") or "",
            status=(fresh or {}).get("status") or doc.get("status"),
            end_reason=end_reason,
            winner_id=(fresh or {}).get("winner_id", doc.get("winner_id")),
            team_mode=bool(doc.get("team_mode")),
            winning_team_id=doc.get("winning_team_id"),
            team_mvp_user_id=doc.get("team_mvp_user_id"),
            team_names=doc.get("team_names"),
            player_ids=participants,
            placements=doc.get("placements"),
            points_awarded=pa,
        )
    except Exception:
        logger.exception("match audit emit failed match_id=%s", match_id)


def finalize_match(snapshot: Dict[str, Any]) -> None:
    """
    snapshot keys:
      match_id, chat_id, game_mode, started, started_at, turn_count,
      participant_ids (list), finish_order (list), end_reason,
      abandon_user_id (optional)
    """
    db = get_database()
    if db is None:
        return

    match_id = snapshot.get("match_id")
    chat_id = snapshot.get("chat_id")
    if not match_id or chat_id is None:
        logger.debug("finalize_match skipped: missing match_id or chat_id")
        return

    started = bool(snapshot.get("started"))
    started_at = snapshot.get("started_at")
    turn_count = int(snapshot.get("turn_count") or 0)
    participants: List[int] = list(snapshot.get("participant_ids") or [])
    finish_order: List[int] = list(snapshot.get("finish_order") or [])
    end_reason = snapshot.get("end_reason") or "unknown"
    game_mode = snapshot.get("game_mode") or ""
    chat_title = snapshot.get("chat_title") or ""
    abandon_uid = snapshot.get("abandon_user_id")
    team_mode = bool(snapshot.get("team_mode"))
    winning_team_id = snapshot.get("winning_team_id")
    team_members = snapshot.get("team_members") or {"A": [], "B": []}
    team_size = int(snapshot.get("team_size") or 0)
    team_names = snapshot.get("team_names") or {"A": "", "B": ""}
    team_mvp_user_id = snapshot.get("team_mvp_user_id")

    pset: Set[int] = set(participants)
    for uid in finish_order:
        pset.add(uid)
    participants = list(pset)

    min_p = max(2, MIN_VALID_PLAYERS_FOR_POINTS)
    min_t = max(0, MIN_VALID_TURNS_FOR_POINTS)
    valid_counts = (
        started
        and len(participants) >= min_p
        and turn_count >= min_t
        and end_reason not in _END_NO_REWARD
    )

    status = _match_status(end_reason, started, finish_order, valid_counts)
    if team_mode and valid_counts and str(winning_team_id or "").upper() in ("A", "B"):
        status = "completed"

    logger.info(f"Match {match_id}: status={status}, started={started}, valid_counts={valid_counts}, finish_order={finish_order}, end_reason={end_reason}")

    ended_at = utc_now().isoformat()
    placements = _build_placements(finish_order)
    if team_mode and str(winning_team_id or "").upper() in ("A", "B"):
        wt = team_members.get(str(winning_team_id).upper()) or []
        winner_id = int(wt[0]) if wt else None
    else:
        winner_id = finish_order[0] if finish_order else None

    doc = {
        "_id": match_id,
        "chat_id": chat_id,
        "chat_title": str(chat_title).strip(),
        "game_mode": game_mode,
        "status": status,
        "winner_id": winner_id,
        "player_ids": participants,
        "placements": placements,
        "points_awarded": {},
        "started_at": _iso(started_at),
        "ended_at": ended_at,
        "turn_count": turn_count,
        "created_at": ended_at,
        "team_mode": team_mode,
        "team_size": team_size,
        "team_members": team_members,
        "team_names": team_names,
        "winning_team_id": winning_team_id,
        "team_mvp_user_id": team_mvp_user_id,
    }

    try:
        if db.matches.find_one({"_id": match_id}, projection=["_id"]):
            logger.debug("finalize_match: match %s already recorded", match_id)
            return
        db.matches.insert_one(doc)
    except DuplicateKeyError:
        logger.debug("finalize_match: match %s duplicate insert", match_id)
        return
    except Exception:
        logger.exception("finalize_match: failed to insert match %s", match_id)
        return

    if status != "completed":
        # Special handling for 2-player game where someone left
        if end_reason == "player_left_2p" and finish_order and len(finish_order) == 1:
            # Award points normally: winner gets full points, leaver gets penalty
            if team_mode:
                _award_completed_team_match(
                    db,
                    match_id,
                    participants,
                    team_members,
                    winning_team_id,
                    team_mvp_user_id,
                )
            else:
                _award_completed_match(db, match_id, participants, finish_order)
            from services.leaderboard_service import invalidate_public_leaderboard_cache
            invalidate_public_leaderboard_cache()

            # Apply abandon penalty to the leaver
            leaver_id = None
            for pid in participants:
                if pid not in finish_order:
                    leaver_id = pid
                    break
            
            if leaver_id:
                penalty = -abs(ABANDON_PENALTY)
                deltas = [(penalty, "abandon_penalty")]
                stat_deltas = {"penalties_count": 1, "abandoned_games": 1}
                _apply_points_bundle(db, match_id, leaver_id, deltas, stat_deltas, streak_override=0)
        else:
            _apply_abandon_penalty(db, match_id, end_reason, abandon_uid)
        _emit_match_audit(db, match_id, doc, participants, end_reason)
        return

    if team_mode:
        _award_completed_team_match(
            db,
            match_id,
            participants,
            team_members,
            winning_team_id,
            team_mvp_user_id,
        )
    else:
        _award_completed_match(db, match_id, participants, finish_order)

    from services.leaderboard_service import invalidate_public_leaderboard_cache
    invalidate_public_leaderboard_cache()
    _emit_match_audit(db, match_id, doc, participants, end_reason)


def _ledger_insert(db: Database, match_id: str, user_id: int, delta: int, reason: str) -> bool:
    try:
        db.point_ledger.insert_one(
            {
                "match_id": match_id,
                "user_id": user_id,
                "delta": delta,
                "reason": reason,
                "created_at": utc_now().isoformat(),
            }
        )
        return True
    except DuplicateKeyError:
        return False
    except Exception as exc:
        logger.warning("ledger insert failed: %s", exc)
        return False


def _ensure_player_stats(db: Database, user_id: int) -> None:
    db.player_stats.update_one(
        {"_id": user_id},
        {"$setOnInsert": {**default_player_stats_doc(user_id), "created_at": utc_now().isoformat()}},
        upsert=True,
    )


def _apply_points_bundle(
    db: Database,
    match_id: str,
    user_id: int,
    deltas: List[tuple],
    stat_deltas: Dict[str, int],
    streak_override: Optional[int] = None,
) -> int:
    """deltas: list of (delta, reason). Returns sum of successfully logged point deltas."""
    logger.info(f"_apply_points_bundle called: user_id={user_id}, match_id={match_id}, deltas={deltas}, stat_deltas={stat_deltas}")
    
    if is_leaderboard_banned(user_id):
        logger.info(f"User {user_id} is leaderboard banned, returning 0 points")
        return 0
    total = 0
    for delta, reason in deltas:
        if delta and _ledger_insert(db, match_id, user_id, delta, reason):
            total += delta
            logger.info(f"Applied {delta} points for user {user_id}, reason: {reason}")
        else:
            logger.warning(f"Failed to apply {delta} points for user {user_id}, reason: {reason}")
    if not total and not stat_deltas and streak_override is None:
        logger.info(f"No points to apply for user {user_id}: total={total}, stat_deltas={stat_deltas}, streak_override={streak_override}")
        return 0
    _ensure_player_stats(db, user_id)
    cur = fetch_player_stats_document(db, user_id) or {}
    wb = week_bucket()
    mb = month_bucket()
    cur_week = (cur.get("week_bucket") or "").strip()
    cur_month = (cur.get("month_bucket") or "").strip()
    cur_season = (cur.get("season_id") or "").strip()

    new_weekly = int(cur.get("weekly_points") or 0) + total
    if cur_week and cur_week != wb:
        new_weekly = total
    new_monthly = int(cur.get("monthly_points") or 0) + total
    if cur_month and cur_month != mb:
        new_monthly = total
    new_season_pts = int(cur.get("season_points") or 0) + total
    if cur_season and cur_season != SEASON_ID:
        new_season_pts = total

    patch = {
        "total_points": int(cur.get("total_points") or 0) + total,
        "season_points": new_season_pts,
        "weekly_points": new_weekly,
        "monthly_points": new_monthly,
        "week_bucket": wb,
        "month_bucket": mb,
        "season_id": SEASON_ID,
        "updated_at": utc_now().isoformat(),
        "last_played_at": utc_now().isoformat(),
    }
    try:
        urow = db.users.find_one({"_id": user_id}, projection=["username", "display_name"])
        if urow:
            un = (urow.get("username") or "").strip()
            dn = (urow.get("display_name") or "").strip()
            if un:
                patch["username"] = un
            if dn:
                patch["display_name"] = dn
    except Exception:
        logger.debug("users lookup for player_stats patch failed user_id=%s", user_id)
    for k, v in stat_deltas.items():
        patch[k] = int(cur.get(k) or 0) + int(v)
    if streak_override is not None:
        patch["current_win_streak"] = streak_override
        patch["best_win_streak"] = max(
            int(cur.get("best_win_streak") or 0), streak_override
        )
    try:
        db.player_stats.update_one({"_id": user_id}, {"$set": patch})
    except Exception:
        logger.exception("player_stats update failed user_id=%s", user_id)
    return total


def _streak_bonus(streak_after: int) -> int:
    b = 0
    if streak_after >= 5:
        b += STREAK_BONUS_5
    elif streak_after >= 3:
        b += STREAK_BONUS_3
    return b


def _apply_abandon_penalty(
    db: Database, match_id: str, end_reason: str, abandon_user_id: Optional[int]
):
    if end_reason != "abandoned_timeout" or not abandon_user_id:
        return
    penalty = -abs(ABANDON_PENALTY)
    deltas = [(penalty, "abandon_penalty")]
    stat_deltas = {"penalties_count": 1, "abandoned_games": 1}
    _apply_points_bundle(
        db, match_id, abandon_user_id, deltas, stat_deltas, streak_override=0
    )


def _award_completed_match(
    db: Database,
    match_id: str,
    participants: List[int],
    finish_order: List[int],
):
    large_bonus = LARGE_MATCH_BONUS if len(participants) >= LARGE_MATCH_MIN_PLAYERS else 0
    points_map: Dict[str, int] = {}

    # Get game mode from match document
    match_doc = db.matches.find_one({"_id": match_id}, projection=["game_mode"])
    game_mode = (match_doc or {}).get("game_mode", "") if match_doc else ""
    participation_points = SUDDEN_DEATH_PARTICIPATION_POINTS if game_mode == "sudden_death" else PARTICIPATION_POINTS
    
    logger.info(f"Awarding points for match {match_id}: mode={game_mode}, participants={len(participants)}, finish_order={len(finish_order)}")
    
    for uid in participants:
        bundles = [(participation_points, "participation")]
        if large_bonus:
            bundles.append((large_bonus, "large_match"))
        stat_d = {"games_played": 1}
        if finish_order and uid == finish_order[0]:
            stat_d["games_won"] = 1
        else:
            stat_d["games_lost"] = 1

        streak_ov = 0
        
        if finish_order and uid == finish_order[0]:
            cur = fetch_player_stats_document(db, uid)
            prev = int(cur.get("current_win_streak") or 0) if cur else 0
            streak_ov = prev + 1
            
            # Enhanced points for Sudden Death mode
            if game_mode == "sudden_death":
                bundles.append((SUDDEN_DEATH_WIN_POINTS, "sudden_death_win"))
            else:
                bundles.append((WIN_POINTS, "win"))
                
            sb_b = _streak_bonus(streak_ov)
            if sb_b:
                bundles.append((sb_b, "streak_bonus"))
        
        # In Sudden Death mode, only winner gets points (no 2nd/3rd place)
        if game_mode != "sudden_death":
            if len(finish_order) > 1 and uid == finish_order[1]:
                bundles.append((SECOND_PLACE_POINTS, "second_place"))
            if len(finish_order) > 2 and uid == finish_order[2]:
                bundles.append((THIRD_PLACE_POINTS, "third_place"))

        applied = _apply_points_bundle(db, match_id, uid, bundles, stat_d, streak_override=streak_ov)
        points_map[str(uid)] = applied
        logger.info(f"User {uid} awarded {applied} points in match {match_id}, bundles: {bundles}")

    try:
        db.matches.update_one({"_id": match_id}, {"$set": {"points_awarded": points_map}})
    except Exception:
        logger.exception("failed to patch points_awarded for match %s", match_id)


def _award_completed_team_match(
    db: Database,
    match_id: str,
    participants: List[int],
    team_members: Dict[str, List[int]],
    winning_team_id: Optional[str],
    team_mvp_user_id: Optional[int],
):
    points_map: Dict[str, int] = {}
    win_tid = (winning_team_id or "").upper()
    winners = set(int(x) for x in (team_members.get(win_tid) or []))
    all_p = set(int(x) for x in participants)
    large_bonus = LARGE_MATCH_BONUS if len(participants) >= LARGE_MATCH_MIN_PLAYERS else 0

    for uid in sorted(all_p):
        bundles = [(PARTICIPATION_POINTS, "team_participation")]
        if large_bonus:
            bundles.append((large_bonus, "team_large_match"))
        stat_d = {
            "games_played": 1,
            "team_matches_played": 1,
        }
        if uid in winners:
            bundles.append((TEAM_WIN_POINTS, "team_win"))
            stat_d["games_won"] = 1
            stat_d["team_wins"] = 1
            cur = fetch_player_stats_document(db, uid)
            prev = int(cur.get("team_current_win_streak") or 0) if cur else 0
            team_streak = prev + 1
            streak_bonus = _streak_bonus(team_streak)
            if streak_bonus:
                bundles.append((streak_bonus, "team_streak_bonus"))
        else:
            bundles.append((TEAM_LOSS_POINTS, "team_loss"))
            stat_d["games_lost"] = 1
            stat_d["team_losses"] = 1
            team_streak = 0
        if team_mvp_user_id is not None and int(team_mvp_user_id) == uid:
            bundles.append((TEAM_MVP_BONUS, "team_mvp_bonus"))
            stat_d["team_mvp_count"] = 1

        # Store team streak independently while preserving solo streak mechanics.
        _ensure_player_stats(db, uid)
        cur = fetch_player_stats_document(db, uid) or {}
        stat_d["team_current_win_streak"] = team_streak - int(cur.get("team_current_win_streak") or 0)
        stat_d["team_best_win_streak"] = max(
            int(cur.get("team_best_win_streak") or 0), team_streak
        ) - int(cur.get("team_best_win_streak") or 0)

        applied = _apply_points_bundle(db, match_id, uid, bundles, stat_d, streak_override=None)
        points_map[str(uid)] = applied

    try:
        db.matches.update_one({"_id": match_id}, {"$set": {"points_awarded": points_map}})
    except Exception:
        logger.exception("failed to patch team points_awarded for match %s", match_id)


def apply_abandon_penalty_points(user_id: int, amount: int) -> bool:
    """
    Apply immediate abandon penalty points to a player.
    Used for /leave in 3+ player games where game continues.
    """
    db = get_database()
    if db is None:
        return False
    try:
        uid = int(user_id)
        amt = int(amount)
    except (TypeError, ValueError):
        return False
    if amt == 0:
        return False
    
    # Create a dummy match_id for penalty tracking
    match_id = "abandon_penalty_%s" % uuid.uuid4().hex
    
    if not _ledger_insert(db, match_id, uid, amt, "abandon_penalty"):
        return False
    
    _ensure_player_stats(db, uid)
    cur = fetch_player_stats_document(db, uid) or {}
    wb = week_bucket()
    mb = month_bucket()
    cur_week = (cur.get("week_bucket") or "").strip()
    cur_month = (cur.get("month_bucket") or "").strip()
    cur_season = (cur.get("season_id") or "").strip()

    # Apply penalty to all time buckets
    new_weekly = int(cur.get("weekly_points") or 0) + amt
    if cur_week and cur_week != wb:
        new_weekly = amt
    new_monthly = int(cur.get("monthly_points") or 0) + amt
    if cur_month and cur_month != mb:
        new_monthly = amt
    new_season_pts = int(cur.get("season_points") or 0) + amt
    if cur_season and cur_season != SEASON_ID:
        new_season_pts = amt

    patch = {
        "total_points": int(cur.get("total_points") or 0) + amt,
        "season_points": new_season_pts,
        "weekly_points": new_weekly,
        "monthly_points": new_monthly,
        "week_bucket": wb,
        "month_bucket": mb,
        "season_id": SEASON_ID,
        "updated_at": utc_now().isoformat(),
        "penalties_count": int(cur.get("penalties_count") or 0) + 1,
        "abandoned_games": int(cur.get("abandoned_games") or 0) + 1,
        "current_win_streak": 0,  # Reset streak on abandon
    }
    
    try:
        db.player_stats.update_one({"_id": uid}, {"$set": patch})
        return True
    except Exception:
        return False


def apply_admin_gift_points(user_id: int, amount: int) -> bool:
    """
    Add gift points to all rolling buckets (same rules as normal point gains).
    Does not honor stats_banned (admin override).
    """
    db = get_database()
    if db is None:
        return False
    try:
        uid = int(user_id)
        amt = int(amount)
    except (TypeError, ValueError):
        return False
    if amt == 0:
        return False
    mid = "admin_gift_%s" % uuid.uuid4().hex
    if not _ledger_insert(db, mid, uid, amt, "admin_gift"):
        return False
    _ensure_player_stats(db, uid)
    cur = fetch_player_stats_document(db, uid) or {}
    wb = week_bucket()
    mb = month_bucket()
    cur_week = (cur.get("week_bucket") or "").strip()
    cur_month = (cur.get("month_bucket") or "").strip()
    cur_season = (cur.get("season_id") or "").strip()

    new_weekly = int(cur.get("weekly_points") or 0) + amt
    if cur_week and cur_week != wb:
        new_weekly = amt
    new_monthly = int(cur.get("monthly_points") or 0) + amt
    if cur_month and cur_month != mb:
        new_monthly = amt
    new_season_pts = int(cur.get("season_points") or 0) + amt
    if cur_season and cur_season != SEASON_ID:
        new_season_pts = amt

    patch = {
        "total_points": int(cur.get("total_points") or 0) + amt,
        "season_points": new_season_pts,
        "weekly_points": new_weekly,
        "monthly_points": new_monthly,
        "week_bucket": wb,
        "month_bucket": mb,
        "season_id": SEASON_ID,
        "updated_at": utc_now().isoformat(),
    }
    try:
        urow = db.users.find_one({"_id": uid}, projection=["username", "display_name"])
        if urow:
            un = (urow.get("username") or "").strip()
            dn = (urow.get("display_name") or "").strip()
            if un:
                patch["username"] = un
            if dn:
                patch["display_name"] = dn
    except Exception:
        logger.debug("users lookup for gift patch failed user_id=%s", uid)
    try:
        db.player_stats.update_one({"_id": uid}, {"$set": patch})
    except Exception:
        logger.exception("apply_admin_gift_points player_stats update failed uid=%s", uid)
        return False
    return True


def increment_cards_played(telegram_user) -> None:
    db = get_database()
    if db is None or telegram_user is None:
        return
    uid = telegram_user.id
    user_service.ensure_user_row(telegram_user)
    try:
        _ensure_player_stats(db, uid)
        db.player_stats.update_one(
            {"_id": uid},
            {
                "$inc": {"cards_played": 1},
                "$set": {"updated_at": utc_now().isoformat()},
            },
        )
    except Exception:
        logger.exception("increment_cards_played failed uid=%s", uid)
