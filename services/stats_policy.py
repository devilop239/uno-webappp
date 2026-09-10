# -*- coding: utf-8 -*-
"""Leaderboard / match points policy (banned cheaters)."""

import logging
from typing import Optional

from db.mongo_client import get_database

logger = logging.getLogger(__name__)


def is_leaderboard_banned(user_id: int) -> bool:
    """True if this user must not receive match points or appear on leaderboards."""
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        return False
    db = get_database()
    if db is None:
        return False
    try:
        row = db.player_stats.find_one({"_id": uid}, projection=["stats_banned"])
        return bool(row and row.get("stats_banned"))
    except Exception:
        logger.exception("is_leaderboard_banned failed user_id=%s", uid)
        return False
