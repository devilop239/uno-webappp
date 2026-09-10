# -*- coding: utf-8 -*-
"""Bot owner / sudo ACL (config + MongoDB `bot_config`)."""

import logging
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set

if TYPE_CHECKING:
    from aiogram import Bot
    from aiogram.types import Message

from config import ADMIN_LIST, BOT_OWNER_IDS, DEFAULT_BOT_OWNER_ID
from db.mongo_client import get_database

logger = logging.getLogger(__name__)

_CONFIG_DOC = "sudo_config"


def owner_ids() -> Set[int]:
    """Telegram user IDs allowed owner-only commands (add/remove/list sudo)."""
    owners: Set[int] = {int(DEFAULT_BOT_OWNER_ID)}
    if BOT_OWNER_IDS:
        owners |= set(int(x) for x in BOT_OWNER_IDS)
        return owners
    if ADMIN_LIST:
        owners |= set(int(x) for x in ADMIN_LIST)
        return owners
    return owners


def is_owner(user_id: int) -> bool:
    return int(user_id) in owner_ids()


def _extra_sudo_ids_raw() -> List[int]:
    db = get_database()
    if db is None:
        return []
    try:
        row = db.bot_config.find_one({"_id": _CONFIG_DOC})
        if not row:
            return []
        out = []
        for x in row.get("extra_sudo_ids") or []:
            try:
                out.append(int(x))
            except (TypeError, ValueError):
                continue
        return out
    except Exception:
        logger.exception("admin_acl read extra_sudo_ids")
        return []


def extra_sudo_ids() -> Set[int]:
    return set(_extra_sudo_ids_raw())


def is_sudo(user_id: int) -> bool:
    uid = int(user_id)
    if is_owner(uid):
        return True
    return uid in extra_sudo_ids()


def add_extra_sudo(user_id: int) -> bool:
    db = get_database()
    if db is None:
        return False
    uid = int(user_id)
    try:
        cur = list(_extra_sudo_ids_raw())
        if uid in cur:
            return True
        cur.append(uid)
        db.bot_config.update_one(
            {"_id": _CONFIG_DOC},
            {"$set": {"extra_sudo_ids": cur}},
            upsert=True,
        )
        return True
    except Exception:
        logger.exception("add_extra_sudo failed user_id=%s", uid)
        return False


def remove_extra_sudo(user_id: int) -> bool:
    db = get_database()
    if db is None:
        return False
    uid = int(user_id)
    try:
        cur = [x for x in _extra_sudo_ids_raw() if x != uid]
        db.bot_config.update_one(
            {"_id": _CONFIG_DOC},
            {"$set": {"extra_sudo_ids": cur}},
            upsert=True,
        )
        return True
    except Exception:
        logger.exception("remove_extra_sudo failed user_id=%s", uid)
        return False


def all_sudo_records() -> List[Dict[str, Any]]:
    """Owner + extra sudo rows with best-known profile from `users`."""
    db = get_database()
    owners = sorted(owner_ids())
    extra = sorted(extra_sudo_ids() - owner_ids())
    seen = set()
    ordered: List[int] = []
    for uid in owners + extra:
        if uid in seen:
            continue
        seen.add(uid)
        ordered.append(uid)

    rows: List[Dict[str, Any]] = []
    for uid in ordered:
        role = "owner" if uid in owner_ids() else "sudo"
        uname = ""
        dname = ""
        if db is not None:
            try:
                urow = db.users.find_one({"_id": uid}, projection=["username", "display_name"])
                if urow:
                    uname = (urow.get("username") or "").strip()
                    dname = (urow.get("display_name") or "").strip()
            except Exception:
                pass
        rows.append(
            {
                "user_id": uid,
                "role": role,
                "username": uname,
                "display_name": dname,
            }
        )
    return rows


def resolve_target_user_id(bot, message, args: List[str]) -> Optional[int]:
    """
    Target from reply_to_message, or first arg as numeric id, or @username / username
    (Telegram get_chat or users collection).
    """
    if message.reply_to_message and message.reply_to_message.from_user:
        return int(message.reply_to_message.from_user.id)

    if not args:
        return None

    raw = args[0].strip()
    if raw.isdigit() or (raw.startswith("-") and raw[1:].isdigit()):
        return int(raw)

    uname = raw.lstrip("@").strip()
    if not uname:
        return None

    try:
        ch = bot.get_chat("@%s" % uname)
        cid = getattr(ch, "id", None)
        if cid is not None:
            return int(cid)
    except Exception:
        pass

    db = get_database()
    if db is None:
        return None
    try:
        esc = re.escape(uname)
        urow = db.users.find_one(
            {"username": {"$regex": "^%s$" % esc, "$options": "i"}},
            projection=["_id"],
        )
        if urow:
            return int(urow["_id"])
    except Exception:
        logger.exception("resolve_target_user_id db lookup")
    return None


async def resolve_target_user_id_async(bot: "Bot", message: "Message", args: List[str]) -> Optional[int]:
    """Async variant using `bot.get_chat` for @username resolution."""
    if message.reply_to_message and message.reply_to_message.from_user:
        return int(message.reply_to_message.from_user.id)

    if not args:
        return None

    raw = args[0].strip()
    if raw.isdigit() or (raw.startswith("-") and raw[1:].isdigit()):
        return int(raw)

    uname = raw.lstrip("@").strip()
    if not uname:
        return None

    try:
        ch = await bot.get_chat("@%s" % uname)
        cid = getattr(ch, "id", None)
        if cid is not None:
            return int(cid)
    except Exception:
        pass

    db = get_database()
    if db is None:
        return None
    try:
        esc = re.escape(uname)
        urow = db.users.find_one(
            {"username": {"$regex": "^%s$" % esc, "$options": "i"}},
            projection=["_id"],
        )
        if urow:
            return int(urow["_id"])
    except Exception:
        logger.exception("resolve_target_user_id_async db lookup")
    return None
