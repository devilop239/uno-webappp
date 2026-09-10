# -*- coding: utf-8 -*-
"""MongoDB connection and index setup. Optional: bot runs without MONGO_URI."""

import logging
from typing import Any, Dict, Optional

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.database import Database
from pymongo.errors import PyMongoError

from config import MONGO_DB_NAME, MONGO_URI
from startup_console import (
    boot_mongo_connecting,
    boot_mongo_failed,
    boot_mongo_ok,
    boot_mongo_skipped,
)

logger = logging.getLogger(__name__)

_client: Optional[MongoClient] = None
_db: Optional[Database] = None


def default_player_stats_doc(user_id: int) -> Dict[str, Any]:
    """Initial `player_stats` document shape (matches former SQL defaults)."""
    return {
        "_id": user_id,
        "user_id": user_id,
        "total_points": 0,
        "season_points": 0,
        "weekly_points": 0,
        "monthly_points": 0,
        "games_played": 0,
        "games_won": 0,
        "games_lost": 0,
        "current_win_streak": 0,
        "best_win_streak": 0,
        "draws": 0,
        "abandoned_games": 0,
        "penalties_count": 0,
        "cards_played": 0,
        "team_matches_played": 0,
        "team_wins": 0,
        "team_losses": 0,
        "team_mvp_count": 0,
        "team_current_win_streak": 0,
        "team_best_win_streak": 0,
        "week_bucket": "",
        "month_bucket": "",
        "season_id": "",
        "username": "",
        "display_name": "",
    }


def fetch_player_stats_document(db: Database, user_id: int) -> Optional[Dict[str, Any]]:
    """Return a plain dict for one player_stats row, or None. Sets user_id for callers that expect it."""
    try:
        row = db.player_stats.find_one({"_id": user_id})
        if not row:
            return None
        out = dict(row)
        out.setdefault("user_id", out.get("_id"))
        return out
    except Exception:
        logger.exception("fetch_player_stats_document failed user_id=%s", user_id)
        return None


def _ensure_indexes(db: Database) -> None:
    """Create indexes in background to avoid blocking startup on new VPS deployments."""
    try:
        ps = db.player_stats
        ps.create_index([("total_points", DESCENDING)], background=True)
        ps.create_index([("week_bucket", ASCENDING), ("weekly_points", DESCENDING)], background=True)
        ps.create_index([("month_bucket", ASCENDING), ("monthly_points", DESCENDING)], background=True)
        ps.create_index([("season_id", ASCENDING), ("season_points", DESCENDING)], background=True)
        ps.create_index([("stats_banned", ASCENDING)], background=True)  # For filtering banned users
        ps.create_index([("username", ASCENDING)], background=True)  # For username lookups
        db.matches.create_index([("chat_id", ASCENDING)], background=True)
        db.matches.create_index([("ended_at", DESCENDING)], background=True)
        db.matches.create_index([("player_ids", ASCENDING)], background=True)
        db.matches.create_index([("chat_id", ASCENDING), ("chat_title", ASCENDING)], background=True)  # For chat title lookups
        db.users.create_index([("username", ASCENDING)], background=True)  # For username searches
        db.users.create_index([("dm_started", ASCENDING)], background=True)  # For DM user filtering
        db.private_games.create_index([("status", ASCENDING), ("updated_at", DESCENDING)], background=True)
        db.private_games.create_index([("player1_id", ASCENDING), ("status", ASCENDING)], background=True)
        db.private_games.create_index([("player2_id", ASCENDING), ("status", ASCENDING)], background=True)
        db.private_user_games.create_index([("user_id", ASCENDING)], unique=True, background=True)
        db.private_user_games.create_index([("game_id", ASCENDING), ("status", ASCENDING)], background=True)
        db.point_ledger.create_index(
            [("match_id", ASCENDING), ("user_id", ASCENDING), ("reason", ASCENDING)],
            unique=True,
            background=True,
        )
        db.point_ledger.create_index([("user_id", ASCENDING)], background=True)  # For user point queries
        logger.info("MongoDB indexes creation initiated in background")
    except PyMongoError:
        logger.exception("MongoDB ensure_indexes failed")


def get_database() -> Optional[Database]:
    """Return database handle or None if URI missing / connection failed."""
    global _client, _db
    if _db is not None:
        return _db
    uri = (MONGO_URI or "").strip()
    if not uri:
        boot_mongo_skipped()
        logger.info("MongoDB not configured (MONGO_URI empty). Stats persistence disabled.")
        return None
    try:
        boot_mongo_connecting()
        _client = MongoClient(
            uri,
            serverSelectionTimeoutMS=5000,
            maxPoolSize=50,
            minPoolSize=5,
            maxIdleTimeMS=60000,
            connectTimeoutMS=5000,
            socketTimeoutMS=20000,
            retryWrites=True,
            w="majority",
        )
        _client.admin.command("ping")
        _db = _client[MONGO_DB_NAME]
        _ensure_indexes(_db)
        boot_mongo_ok()
        return _db
    except PyMongoError:
        logger.exception("Failed to initialize MongoDB")
        boot_mongo_failed()
        _client = None
        _db = None
        return None


def init_mongo() -> None:
    """Prime connection at import time (same role as former init_supabase)."""
    get_database()


async def close_database() -> None:
    """Close MongoDB client connection if active."""
    global _client, _db
    if _client is not None:
        try:
            _client.close()
        except Exception as e:
            logger.warning("Error closing MongoDB client: %s", e)
        _client = None
        _db = None


__all__ = [
    "default_player_stats_doc",
    "fetch_player_stats_document",
    "get_database",
    "init_mongo",
    "close_database",
]
