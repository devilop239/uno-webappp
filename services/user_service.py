# -*- coding: utf-8 -*-
"""User preferences and Telegram profile sync (MongoDB `users` + `player_stats`)."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from pymongo.errors import DuplicateKeyError

from db.mongo_client import default_player_stats_doc, get_database

logger = logging.getLogger(__name__)

_DEFAULT_LANG = "en_US"


def _ts():
    return datetime.now(timezone.utc).isoformat()


def _tg_display_name(user) -> str:
    if user is None:
        return ""
    parts = [user.first_name or "", user.last_name or ""]
    name = " ".join(p for p in parts if p).strip()
    return name or (user.username or "")


def mark_first_group_interaction(user_id: int, chat_id: int) -> bool:
    """
    Record that this user used the bot in this group chat.
    Returns True only the first time (for optional one-shot hints, e.g. open PM).
    """
    db = get_database()
    if db is None:
        return False
    try:
        uid = int(user_id)
        cid = int(chat_id)
    except (TypeError, ValueError):
        return False
    doc_id = "%d:%d" % (cid, uid)
    try:
        db.group_bot_first_seen.insert_one(
            {
                "_id": doc_id,
                "user_id": uid,
                "chat_id": cid,
                "first_at": _ts(),
            }
        )
        return True
    except DuplicateKeyError:
        return False
    except Exception:
        logger.exception("mark_first_group_interaction failed user_id=%s chat_id=%s", uid, cid)
        return False


def ensure_user_row(telegram_user) -> None:
    """Upsert `users` and ensure `player_stats` row exists."""
    db = get_database()
    if db is None or telegram_user is None:
        return
    uid = telegram_user.id
    uname = getattr(telegram_user, "username", None) or ""
    dname = _tg_display_name(telegram_user)
    now = _ts()
    try:
        db.users.update_one(
            {"_id": uid},
            {
                "$set": {
                    "username": uname,
                    "display_name": dname,
                    "updated_at": now,
                },
                "$setOnInsert": {
                    "lang": _DEFAULT_LANG,
                    "stats_enabled": True,
                    "created_at": now,
                },
            },
            upsert=True,
        )
        db.player_stats.update_one(
            {"_id": uid},
            {"$setOnInsert": {**default_player_stats_doc(uid), "created_at": now}},
            upsert=True,
        )
    except Exception:
        logger.exception("ensure_user_row failed for user_id=%s", uid)


def has_started_bot_in_dm(user_id: int) -> bool:
    """
    True when this user has started the bot in private chat at least once.
    Missing field is treated as False for old rows.
    """
    db = get_database()
    if db is None:
        # Fail-open when persistence is unavailable, so group gameplay is not bricked.
        return True
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        return False
    try:
        row = db.users.find_one({"_id": uid}, projection=["dm_started"])
        if not row:
            return False
        return bool(row.get("dm_started", False))
    except Exception:
        logger.exception("has_started_bot_in_dm failed for user_id=%s", uid)
        return False


def mark_user_started_bot_in_dm(telegram_user) -> None:
    """Idempotently mark this Telegram user as DM-initialized."""
    db = get_database()
    if db is None or telegram_user is None:
        return
    uid = int(telegram_user.id)
    uname = getattr(telegram_user, "username", None) or ""
    dname = _tg_display_name(telegram_user)
    now = _ts()
    try:
        existing = db.users.find_one({"_id": uid}, projection=["dm_started", "dm_started_at"])
        patch = {
            "username": uname,
            "display_name": dname,
            "updated_at": now,
            "dm_started": True,
        }
        if not existing or not existing.get("dm_started_at"):
            patch["dm_started_at"] = now
        db.users.update_one(
            {"_id": uid},
            {
                "$set": patch,
                "$setOnInsert": {
                    "lang": _DEFAULT_LANG,
                    "stats_enabled": True,
                    "created_at": now,
                },
            },
            upsert=True,
        )
        db.player_stats.update_one(
            {"_id": uid},
            {"$setOnInsert": {**default_player_stats_doc(uid), "created_at": now}},
            upsert=True,
        )
    except Exception:
        logger.exception("mark_user_started_bot_in_dm failed for user_id=%s", uid)


def ensure_user_dm_initialized(telegram_user) -> None:
    """Reusable entrypoint for private /start initialization."""
    ensure_user_row(telegram_user)
    mark_user_started_bot_in_dm(telegram_user)


def get_prefs(user_id: int) -> Dict[str, Any]:
    """Return lang and display fields. Statistics are always enabled for all users."""
    db = get_database()
    if db is None:
        return {"lang": _DEFAULT_LANG, "stats_enabled": True}
    try:
        row = db.users.find_one({"_id": user_id}, projection=["lang", "username", "display_name"])
        if not row:
            return {"lang": _DEFAULT_LANG, "stats_enabled": True}
        lang = row.get("lang") or _DEFAULT_LANG
        if lang == "en":
            lang = _DEFAULT_LANG
        return {
            "lang": lang,
            "stats_enabled": True,
            "username": row.get("username"),
            "display_name": row.get("display_name"),
        }
    except Exception:
        logger.exception("get_prefs failed for user_id=%s", user_id)
        return {"lang": _DEFAULT_LANG, "stats_enabled": True}


def load_or_create_prefs(user_id: int) -> Dict[str, Any]:
    """Like get_prefs but inserts stub row if missing (settings screen)."""
    db = get_database()
    if db is None:
        return {"lang": _DEFAULT_LANG, "stats_enabled": True}
    try:
        now = _ts()
        if not db.users.find_one({"_id": user_id}, projection=["_id"]):
            db.users.insert_one(
                {
                    "_id": user_id,
                    "lang": _DEFAULT_LANG,
                    "stats_enabled": True,
                    "username": "",
                    "display_name": "",
                    "created_at": now,
                    "updated_at": now,
                }
            )
            db.player_stats.update_one(
                {"_id": user_id},
                {"$setOnInsert": {**default_player_stats_doc(user_id), "created_at": now}},
                upsert=True,
            )
    except Exception:
        logger.exception("load_or_create_prefs insert failed user_id=%s", user_id)
    return get_prefs(user_id)


def set_lang(user_id: int, locale: str) -> None:
    db = get_database()
    if db is None:
        return
    try:
        db.users.update_one(
            {"_id": user_id},
            {"$set": {"lang": locale, "updated_at": _ts()}},
            upsert=True,
        )
    except Exception:
        logger.exception("set_lang failed user_id=%s", user_id)


def set_stats_enabled(user_id: int, _enabled: bool = True) -> None:
    """Legacy no-op: statistics are always on. Keeps DB row consistent with True."""
    db = get_database()
    if db is None:
        return
    try:
        db.users.update_one(
            {"_id": user_id},
            {
                "$set": {"stats_enabled": True, "updated_at": _ts()},
                "$setOnInsert": {
                    "lang": _DEFAULT_LANG,
                    "username": "",
                    "display_name": "",
                    "created_at": _ts(),
                },
            },
            upsert=True,
        )
    except Exception:
        logger.exception("set_stats_enabled failed user_id=%s", user_id)


def reset_stats_counters(user_id: int) -> None:
    """Reset gameplay counters on `player_stats` (admin / legacy tooling)."""
    db = get_database()
    if db is None:
        return
    try:
        db.player_stats.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "games_played": 0,
                    "games_won": 0,
                    "games_lost": 0,
                    "cards_played": 0,
                    "current_win_streak": 0,
                    "draws": 0,
                    "abandoned_games": 0,
                    "penalties_count": 0,
                    "updated_at": _ts(),
                }
            },
            upsert=False,
        )
    except Exception:
        logger.exception("reset_stats_counters failed user_id=%s", user_id)


def sync_telegram_profile(telegram_user) -> None:
    """Refresh username / display_name from Telegram."""
    db = get_database()
    if db is None or telegram_user is None:
        return
    uid = telegram_user.id
    un = getattr(telegram_user, "username", None) or ""
    dn = _tg_display_name(telegram_user)
    try:
        db.users.update_one(
            {"_id": uid},
            {"$set": {"username": un, "display_name": dn, "updated_at": _ts()}},
        )
        db.player_stats.update_one(
            {"_id": uid},
            {"$set": {"username": un, "display_name": dn, "updated_at": _ts()}},
        )
    except Exception:
        logger.exception("sync_telegram_profile failed user_id=%s", uid)


def get_langs_for_players(player_iter) -> Dict[int, str]:
    """Return user_id -> locale code for in-game multi-locale messages."""
    ids = []
    for p in player_iter:
        if p and p.user:
            ids.append(p.user.id)
    if not ids:
        return {}
    db = get_database()
    if db is None:
        return {i: _DEFAULT_LANG for i in ids}
    try:
        uid_set = list(set(ids))
        out = {i: _DEFAULT_LANG for i in ids}
        for row in db.users.find({"_id": {"$in": uid_set}}, projection=["_id", "lang"]):
            lang = row.get("lang") or _DEFAULT_LANG
            if lang == "en":
                lang = _DEFAULT_LANG
            out[row["_id"]] = lang
        return out
    except Exception:
        logger.exception("get_langs_for_players failed")
        return {i: _DEFAULT_LANG for i in ids}