# -*- coding: utf-8 -*-
"""Owner/sudo-only commands (private). Register before player /stats."""

from __future__ import annotations

import html
import json
import logging
import os
import subprocess
from typing import Optional, Tuple

from aiogram import Bot, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message

from db.mongo_client import get_database
from handlers.filters_acl import OwnerPrivateFilter, SudoPrivateFilter
from services import admin_acl
from services.match_service import apply_admin_gift_points
from loggers import format_user, schedule_audit_telegram
from shared_vars import gm
from tg.helpers import send_message

logger = logging.getLogger(__name__)

router = Router(name="admin")
_ADMIN_SUDO_COMMANDS = ("stats", "reset_full_stats", "gift_points", "ban_user", "restart")
_ADMIN_OWNER_COMMANDS = ("add_sudo", "remove_sudo", "all_sudo")


async def _send_json(bot: Bot, chat_id: int, payload: dict) -> None:
    raw = json.dumps(payload, indent=2, ensure_ascii=False)
    text = "<pre>%s</pre>" % html.escape(raw)
    await bot.send_message(
        chat_id,
        text,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


def _positive_int(s: str) -> Optional[int]:
    try:
        v = int(s)
        return v if v > 0 else None
    except (TypeError, ValueError):
        return None


@router.message(Command("stats"), SudoPrivateFilter())
async def cmd_admin_stats(message: Message, bot: Bot) -> None:
    db = get_database()
    if db is None:
        await _send_json(
            bot,
            message.chat.id,
            {"error": "MongoDB not configured", "mongo_uri_set": False},
        )
        return

    chats_with_games = 0
    players_in_games = set()
    try:
        for _cid, games in gm.chatid_games.items():
            if games:
                chats_with_games += 1
            for g in games:
                for p in g.players:
                    if p.user:
                        players_in_games.add(p.user.id)
    except Exception:
        logger.exception("admin stats game scan")

    try:
        users_count = db.users.count_documents({})
        player_stats_count = db.player_stats.count_documents({})
        matches_count = db.matches.count_documents({})
    except Exception as e:
        await _send_json(bot, message.chat.id, {"error": str(e)})
        return

    owners = sorted(admin_acl.owner_ids())
    extra_sudo = sorted(admin_acl.extra_sudo_ids() - admin_acl.owner_ids())

    await _send_json(
        bot,
        message.chat.id,
        {
            "mongodb": True,
            "users_in_db": users_count,
            "player_stats_rows": player_stats_count,
            "matches_recorded": matches_count,
            "active_group_chats_with_game": chats_with_games,
            "telegram_users_currently_in_a_game": len(players_in_games),
            "bot_owner_user_ids": owners,
            "extra_sudo_user_ids": extra_sudo,
            "total_sudo_effective": len(admin_acl.owner_ids() | admin_acl.extra_sudo_ids()),
        },
    )


@router.message(Command("reset_full_stats"), SudoPrivateFilter())
async def cmd_reset_full_stats(message: Message, bot: Bot) -> None:
    parts = (message.text or "").split(maxsplit=1)
    args = parts[1].split() if len(parts) > 1 else []
    if not args or args[0].upper() != "CONFIRM":
        await bot.send_message(
            message.chat.id,
            "Usage: /reset_full_stats CONFIRM\n"
            "Deletes all player_stats, point_ledger, and matches (irreversible).",
        )
        return
    db = get_database()
    if db is None:
        await bot.send_message(message.chat.id, text="MongoDB not configured.")
        return
    try:
        ps = db.player_stats.delete_many({}).deleted_count
        pl = db.point_ledger.delete_many({}).deleted_count
        mt = db.matches.delete_many({}).deleted_count
        await _send_json(
            bot,
            message.chat.id,
            {
                "ok": True,
                "deleted_player_stats": ps,
                "deleted_point_ledger": pl,
                "deleted_matches": mt,
            },
        )
    except Exception as e:
        logger.exception("reset_full_stats")
        await _send_json(bot, message.chat.id, {"ok": False, "error": str(e)})


async def _parse_gift(message: Message, bot: Bot) -> Tuple[Optional[int], Optional[int], Optional[str]]:
    parts = (message.text or "").split(maxsplit=1)
    args = parts[1].split() if len(parts) > 1 else []
    if len(args) < 1:
        return None, None, "usage"
    pts = _positive_int(args[0].strip())
    if pts is None:
        return None, None, "bad_points"
    if message.reply_to_message and message.reply_to_message.from_user:
        return pts, int(message.reply_to_message.from_user.id), None
    if len(args) < 2:
        return None, None, "need_target"
    tid = await admin_acl.resolve_target_user_id_async(bot, message, args[1:])
    if tid is None:
        return None, None, "target_not_found"
    return pts, tid, None


@router.message(Command("gift_points"))
async def cmd_gift_points(message: Message, bot: Bot) -> None:
    uid = message.from_user.id if message.from_user else 0
    if not admin_acl.is_sudo(uid):
        await bot.send_message(
            message.chat.id,
            "Not authorized. This command requires sudo/owner access.",
        )
        return
    pts, tid, err = await _parse_gift(message, bot)
    if err:
        if err == "usage":
            hint = (
                "Usage: reply to a user with /gift_points 5000\n"
                "or: /gift_points 5000 <user_id|@username>"
            )
        elif err == "bad_points":
            hint = "Invalid points amount (use a positive integer)."
        elif err == "need_target":
            hint = "Reply to the user or pass user id / @username after the amount."
        else:
            hint = "Could not resolve that user."
        await bot.send_message(message.chat.id, text=hint)
        return
    if apply_admin_gift_points(tid, pts):
        schedule_audit_telegram(
            "admin_gift_points",
            action="gift_points",
            actor=format_user(message.from_user),
            target_user_id=tid,
            points=pts,
            chat_type=message.chat.type,
        )
        await _send_json(
            bot,
            message.chat.id,
            {"ok": True, "gifted_user_id": tid, "points": pts},
        )
    else:
        await _send_json(bot, message.chat.id, {"ok": False, "error": "gift_failed"})


@router.message(Command("ban_user"), SudoPrivateFilter())
async def cmd_ban_user(message: Message, bot: Bot) -> None:
    parts = (message.text or "").split(maxsplit=1)
    args = parts[1].split() if len(parts) > 1 else []
    tid = None
    if message.reply_to_message and message.reply_to_message.from_user:
        tid = int(message.reply_to_message.from_user.id)
    elif args:
        tid = await admin_acl.resolve_target_user_id_async(bot, message, args)
    if tid is None:
        await bot.send_message(
            message.chat.id,
            text="Reply to the user or: /ban_user <user_id|@username>",
        )
        return
    db = get_database()
    if db is None:
        await bot.send_message(message.chat.id, text="MongoDB not configured.")
        return
    try:
        from datetime import datetime, timezone

        from db.mongo_client import default_player_stats_doc

        now = datetime.now(timezone.utc).isoformat()
        db.player_stats.update_one(
            {"_id": tid},
            {
                "$set": {
                    "stats_banned": True,
                    "updated_at": now,
                    "banned_at": now,
                    "banned_by": message.from_user.id,
                },
                "$setOnInsert": {**default_player_stats_doc(tid), "created_at": now},
            },
            upsert=True,
        )
        await _send_json(bot, message.chat.id, {"ok": True, "banned_user_id": tid})
    except Exception as e:
        logger.exception("ban_user")
        await _send_json(bot, message.chat.id, {"ok": False, "error": str(e)})


def _owners_configured() -> bool:
    return bool(admin_acl.owner_ids())


@router.message(Command("add_sudo"), OwnerPrivateFilter())
async def cmd_add_sudo(message: Message, bot: Bot) -> None:
    if not _owners_configured():
        await bot.send_message(
            message.chat.id,
            text="Set BOT_OWNER_IDS (or admin_list) in config first.",
        )
        return
    parts = (message.text or "").split(maxsplit=1)
    args = parts[1].split() if len(parts) > 1 else []
    tid = await admin_acl.resolve_target_user_id_async(bot, message, args)
    if tid is None:
        await bot.send_message(
            message.chat.id,
            text="Usage: /add_sudo <user_id|@username>",
        )
        return
    if admin_acl.add_extra_sudo(tid):
        await _send_json(bot, message.chat.id, {"ok": True, "added_sudo_user_id": tid})
    else:
        await _send_json(bot, message.chat.id, {"ok": False, "error": "mongo_failed"})


@router.message(Command("remove_sudo"), OwnerPrivateFilter())
async def cmd_remove_sudo(message: Message, bot: Bot) -> None:
    if not _owners_configured():
        await bot.send_message(
            message.chat.id,
            text="Set BOT_OWNER_IDS (or admin_list) in config first.",
        )
        return
    parts = (message.text or "").split(maxsplit=1)
    args = parts[1].split() if len(parts) > 1 else []
    tid = await admin_acl.resolve_target_user_id_async(bot, message, args)
    if tid is None:
        await bot.send_message(
            message.chat.id,
            text="Usage: /remove_sudo <user_id|@username>",
        )
        return
    if tid in admin_acl.owner_ids():
        await _send_json(
            bot,
            message.chat.id,
            {"ok": False, "error": "cannot_remove_owner_from_sudo_list", "user_id": tid},
        )
        return
    if admin_acl.remove_extra_sudo(tid):
        await _send_json(bot, message.chat.id, {"ok": True, "removed_sudo_user_id": tid})
    else:
        await _send_json(bot, message.chat.id, {"ok": False, "error": "mongo_failed"})


@router.message(Command("all_sudo"), OwnerPrivateFilter())
async def cmd_all_sudo(message: Message, bot: Bot) -> None:
    if not _owners_configured():
        await bot.send_message(
            message.chat.id,
            text="Set BOT_OWNER_IDS (or admin_list) in config first.",
        )
        return
    await _send_json(bot, message.chat.id, {"sudo_users": admin_acl.all_sudo_records()})


@router.message(Command("restart"))
async def cmd_restart(message: Message, bot: Bot) -> None:
    """Restart bot and pull latest changes from GitHub."""
    uid = message.from_user.id if message.from_user else 0
    
    # Security check - only sudo/owner can restart
    if not admin_acl.is_sudo(uid):
        await bot.send_message(
            message.chat.id,
            "Not authorized. This command requires sudo/owner access.",
        )
        return
    
    # Only work in private chat
    if message.chat.type != "private":
        await bot.send_message(
            message.chat.id,
            "This command works only in private chat with the bot.",
        )
        return
    
    await bot.send_message(
        message.chat.id,
        "🔄 **Restarting bot and pulling latest changes...**\n\n"
        "This will:\n"
        "1. Pull latest changes from GitHub\n"
        "2. Restart the bot\n"
        "3. Apply all updates\n\n"
        "Please wait ~30 seconds...",
        parse_mode=ParseMode.HTML
    )
    
    try:
        # Get current working directory (should be bot directory)
        bot_dir = os.getcwd()
        
        # Pull latest changes from GitHub
        logger.info(f"Pulling latest changes from GitHub in {bot_dir}")
        pull_result = subprocess.run(
            ["git", "pull", "origin", "master"],
            cwd=bot_dir,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if pull_result.returncode != 0:
            await bot.send_message(
                message.chat.id,
                f"❌ **Git pull failed:**\n\n```\n{pull_result.stderr}\n```",
                parse_mode=ParseMode.HTML
            )
            return
        
        # Log the pull result
        logger.info(f"Git pull result: {pull_result.stdout}")
        
        await bot.send_message(
            message.chat.id,
            f"✅ **Changes pulled successfully:**\n\n```\n{pull_result.stdout[-200:]}\n```\n\n"
            "🔄 **Restarting bot now...**",
            parse_mode=ParseMode.HTML
        )
        
        # Schedule restart after a short delay to allow message to be sent
        import asyncio
        import signal
        
        async def delayed_restart():
            await asyncio.sleep(2)
            logger.info("Restarting bot due to /restart command")
            # Send SIGTERM to self to trigger graceful shutdown
            os.kill(os.getpid(), signal.SIGTERM)
        
        # Schedule the restart
        asyncio.create_task(delayed_restart())
        
    except subprocess.TimeoutExpired:
        await bot.send_message(
            message.chat.id,
            "❌ **Git pull timed out** after 30 seconds. Please check manually.",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.exception("Error during restart command")
        await bot.send_message(
            message.chat.id,
            f"❌ **Restart failed:**\n\n```\n{str(e)}\n```",
            parse_mode=ParseMode.HTML
        )


@router.message(Command(*_ADMIN_SUDO_COMMANDS, *_ADMIN_OWNER_COMMANDS))
async def cmd_admin_access_fallback(message: Message, bot: Bot) -> None:
    """
    Fallback for private-only admin commands so users get a clear reason instead of
    silent 'not handled' when called in group or by unauthorized users.
    """
    raw = (message.text or "").strip()
    cmd = raw.split()[0].lstrip("/").split("@")[0].lower() if raw else ""
    if not cmd:
        return
    if cmd == "gift_points":
        uid = message.from_user.id if message.from_user else 0
        if not admin_acl.is_sudo(uid):
            await bot.send_message(
                message.chat.id,
                "Not authorized. This command requires sudo/owner access.",
            )
        return
    if message.chat.type != "private":
        await bot.send_message(
            message.chat.id,
            "These admin commands work only in private chat with the bot.",
        )
        return
    uid = message.from_user.id if message.from_user else 0
    if cmd in _ADMIN_OWNER_COMMANDS and not admin_acl.is_owner(uid):
        await bot.send_message(
            message.chat.id,
            "Not authorized. This command is owner-only.",
        )
        return
    if cmd in _ADMIN_SUDO_COMMANDS and not admin_acl.is_sudo(uid):
        await bot.send_message(
            message.chat.id,
            "Not authorized. This command requires sudo/owner access.",
        )
        return
