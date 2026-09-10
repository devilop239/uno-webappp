# -*- coding: utf-8 -*-
"""Broadcast commands for sudo/owner operators."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from uuid import uuid4

from aiogram import Bot, F, Router
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramRetryAfter
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from db.mongo_client import get_database
from loggers import format_user, schedule_audit_telegram
from services import admin_acl

router = Router(name="broadcast")


# =============================================================================
# Auto-delete / tracked-message support
#
# Every message a broadcast sends is recorded as (chat_id, message_id) under a
# BroadcastJob. That job backs two things:
#   - the "🗑 Delete Broadcast" inline button attached to every broadcast's
#     status message, letting an operator wipe the whole run on demand
#   - optional auto-delete, when a duration is supplied (see _run_broadcast)
# =============================================================================
_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600}
_DURATION_RE = re.compile(r"^(\d+)\s*(s|m|h)$", re.IGNORECASE)
_DELETE_CONCURRENCY = 10


@dataclass
class BroadcastJob:
    id: str
    initiator_id: int
    auto_delete_seconds: Optional[int] = None
    sent: List[Tuple[int, int]] = field(default_factory=list)  # (chat_id, message_id)
    deleted: bool = False
    delete_task: Optional[asyncio.Task] = None


_JOBS: Dict[str, BroadcastJob] = {}


def _parse_duration(text: str) -> Optional[int]:
    """Parses '10m' / '1h' / '30s' into seconds. Returns None if not a duration."""
    if not text:
        return None
    match = _DURATION_RE.match(text.strip())
    if not match:
        return None
    value, unit = match.groups()
    return int(value) * _UNIT_SECONDS[unit.lower()]


def _format_duration(seconds: int) -> str:
    hrs, rem = divmod(seconds, 3600)
    mins, secs = divmod(rem, 60)
    parts = [f"{hrs}h" if hrs else "", f"{mins}m" if mins else "", f"{secs}s" if secs else ""]
    return " ".join(p for p in parts if p) or "0s"


def _delete_button(broadcast_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🗑 Delete Broadcast", callback_data=f"delbc:{broadcast_id}")]]
    )


async def _delete_job_messages(bot: Bot, job: BroadcastJob) -> Tuple[int, int]:
    """Deletes every tracked message for a job. Returns (deleted, failed)."""
    deleted = 0
    failed = 0
    semaphore = asyncio.Semaphore(_DELETE_CONCURRENCY)

    async def _delete_one(chat_id: int, message_id: int) -> None:
        nonlocal deleted, failed
        async with semaphore:
            try:
                await bot.delete_message(chat_id, message_id)
                deleted += 1
            except Exception:
                failed += 1
            await asyncio.sleep(0.03)

    await asyncio.gather(*(_delete_one(chat_id, message_id) for chat_id, message_id in job.sent))
    return deleted, failed


async def _schedule_auto_delete(
    bot: Bot, job: BroadcastJob, seconds: int, status_chat_id: int, status_message_id: int
) -> None:
    try:
        await asyncio.sleep(seconds)
    except asyncio.CancelledError:
        return

    if job.deleted:
        return

    deleted, failed = await _delete_job_messages(bot, job)
    job.deleted = True
    note = f" ({failed} already gone/failed)" if failed else ""
    try:
        await bot.edit_message_text(
            f"⏱ <b>Temp broadcast expired — auto-deleted.</b>\n\n🗑 Removed from <b>{deleted}</b> chat(s){note}.",
            chat_id=status_chat_id,
            message_id=status_message_id,
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("delbc:"))
async def cb_delete_broadcast(callback: CallbackQuery, bot: Bot) -> None:
    if not callback.from_user or not admin_acl.is_sudo(callback.from_user.id):
        return await callback.answer("Not authorized.", show_alert=True)

    broadcast_id = (callback.data or "").split(":", 1)[1]
    job = _JOBS.get(broadcast_id)

    if not job:
        return await callback.answer(
            "This broadcast is no longer tracked (bot may have restarted).", show_alert=True
        )
    if job.deleted:
        return await callback.answer("Already deleted.", show_alert=True)

    if job.delete_task and not job.delete_task.done():
        job.delete_task.cancel()

    await callback.answer("Deleting broadcasted messages...")
    deleted, failed = await _delete_job_messages(bot, job)
    job.deleted = True

    note = f" ({failed} already gone/failed)" if failed else ""
    try:
        await bot.edit_message_text(
            f"🗑 <b>Broadcast deleted.</b>\n\nRemoved from <b>{deleted}</b> chat(s){note}.",
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        pass


# =============================================================================
# Targets
# =============================================================================
@dataclass(frozen=True)
class BroadcastTargets:
    ids: List[int]
    user_count: int
    chat_count: int


def _is_sudo(message: Message) -> bool:
    user = message.from_user
    return bool(user and admin_acl.is_sudo(user.id))


def _extract_command_text(message: Message) -> str:
    parts = (message.text or "").split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


def _fetch_user_and_chat_sets() -> Tuple[Set[int], Set[int]]:
    db = get_database()
    users: Set[int] = set()
    chats: Set[int] = set()
    if db is None:
        return users, chats

    for uid in db.users.distinct("_id"):
        try:
            users.add(int(uid))
        except (TypeError, ValueError):
            continue

    for cid in db.group_bot_first_seen.distinct("chat_id"):
        try:
            chats.add(int(cid))
        except (TypeError, ValueError):
            continue
    for cid in db.matches.distinct("chat_id"):
        try:
            chats.add(int(cid))
        except (TypeError, ValueError):
            continue
    return users, chats


def _resolve_targets(kind: str) -> BroadcastTargets:
    users, chats = _fetch_user_and_chat_sets()
    if kind == "user":
        ids = sorted(users)
        return BroadcastTargets(ids=ids, user_count=len(ids), chat_count=0)
    if kind == "chat":
        ids = sorted(chats)
        return BroadcastTargets(ids=ids, user_count=0, chat_count=len(ids))
    ids = sorted(users | chats)
    return BroadcastTargets(ids=ids, user_count=len(users), chat_count=len(chats))


# =============================================================================
# Message copy
# =============================================================================
def _usage_text() -> str:
    return (
        "<b>Broadcast usage</b>\n\n"
        "Reply to any message (text, photo, sticker, etc.) with one of:\n\n"
        "<b>Copy (default)</b>\n"
        "• /broadcast_all — all users + all chats\n"
        "• /broadcast_users — users only\n"
        "• /broadcast_chats — group chats only\n\n"
        "<b>Forward (shows “forwarded from”)</b>\n"
        "• /broadcast_all_forward\n"
        "• /broadcast_users_forward\n"
        "• /broadcast_chats_forward\n\n"
        "Or send text directly:\n"
        "<code>/broadcast_users Your message here</code>\n\n"
        "<b>Auto-delete</b> — when replying (not text mode), add a duration "
        "instead of text to wipe the broadcast later:\n"
        "<code>/broadcast_all 1h</code> · <code>/broadcast_chats 30m</code> · "
        "<code>/broadcast_users_forward 10s</code>\n"
        "(s = seconds, m = minutes, h = hours)\n\n"
        "A <b>🗑 Delete Broadcast</b> button is also attached to every run, so you "
        "can wipe it manually at any time.\n\n"
        "Aliases: /broadcast, /broadcast_user, /broadcast_chat"
    )


def _delivery_label(forward: bool) -> str:
    return "forward" if forward else "copy"


def _scope_line(targets: BroadcastTargets, kind: str) -> str:
    """One clear, bolded line showing exactly how many users/chats are targeted."""
    if kind == "user":
        return f"👤 <b>Users:</b> {targets.user_count}"
    if kind == "chat":
        return f"👥 <b>Chats:</b> {targets.chat_count}"
    return (
        f"👤 <b>Users:</b> {targets.user_count}  ·  "
        f"👥 <b>Chats:</b> {targets.chat_count}  ·  "
        f"📊 <b>Total:</b> {len(targets.ids)}"
    )


def _start_message(
    targets: BroadcastTargets, kind: str, *, forward: bool, auto_delete_seconds: Optional[int]
) -> str:
    mode = _delivery_label(forward)
    lines = [
        "📢 <b>Broadcast started</b>",
        f"Delivery: <code>{mode}</code>",
        _scope_line(targets, kind),
    ]
    if auto_delete_seconds:
        lines.append(f"⏱ <b>Auto-delete in:</b> {_format_duration(auto_delete_seconds)}")
    return "\n".join(lines)


def _complete_message(
    targets: BroadcastTargets,
    kind: str,
    *,
    forward: bool,
    ok: int,
    failed: int,
    failed_ids: List[int],
    auto_delete_seconds: Optional[int],
) -> str:
    mode = _delivery_label(forward)
    lines = [
        "<b>✅ Broadcast completed</b>",
        f"Delivery: <code>{mode}</code>",
        _scope_line(targets, kind),
        f"Sent: <code>{ok}</code>  ·  Failed: <code>{failed}</code>",
    ]
    if failed_ids:
        lines.append("Failed IDs (sample): <code>%s</code>" % ", ".join(str(x) for x in failed_ids))
    if auto_delete_seconds:
        lines.append(f"⏱ <b>Auto-delete in:</b> {_format_duration(auto_delete_seconds)}")
    return "\n".join(lines)


# =============================================================================
# Delivery
# =============================================================================
async def _send_to_target(
    bot: Bot,
    target_id: int,
    source_message: Optional[Message],
    inline_text: str,
    *,
    forward: bool,
) -> Optional[int]:
    """Sends once (with one retry on flood-wait). Returns the sent message_id, or None on failure."""
    for attempt in range(2):
        try:
            if source_message is not None:
                if forward:
                    sent = await bot.forward_message(
                        chat_id=target_id,
                        from_chat_id=source_message.chat.id,
                        message_id=source_message.message_id,
                    )
                    # forwardMessage never carries reply_markup (Telegram strips
                    # inline keyboards from forwarded messages by design) — if the
                    # source had buttons, re-attach them on the bot's own copy.
                    if source_message.reply_markup is not None:
                        try:
                            await bot.edit_message_reply_markup(
                                chat_id=target_id,
                                message_id=sent.message_id,
                                reply_markup=source_message.reply_markup,
                            )
                        except Exception:
                            pass  # not fatal — message still delivered, just without buttons
                    return sent.message_id
                result = await bot.copy_message(
                    chat_id=target_id,
                    from_chat_id=source_message.chat.id,
                    message_id=source_message.message_id,
                    reply_markup=source_message.reply_markup,
                )
                return result.message_id
            sent = await bot.send_message(target_id, inline_text, disable_web_page_preview=True)
            return sent.message_id
        except TelegramRetryAfter as exc:
            if attempt == 1:
                return None
            await asyncio.sleep(float(getattr(exc, "retry_after", 1) or 1))
        except Exception:
            return None
    return None


async def _run_broadcast(
    message: Message,
    bot: Bot,
    target_kind: str,
    *,
    forward: bool = False,
) -> None:
    # Non-sudo: silent (no spam in groups or DMs).
    if not _is_sudo(message):
        return
    if not message.chat or message.chat.type != "private":
        await bot.send_message(
            message.chat.id,
            "Broadcast commands work only in <b>private chat</b> with the bot.",
            parse_mode=ParseMode.HTML,
        )
        return

    src = message.reply_to_message
    command_arg = _extract_command_text(message)

    # Auto-delete duration only applies in reply mode. In text mode the
    # remainder is the broadcast body itself, so it's never treated as a
    # duration — no ambiguity, no accidental parsing of message content.
    auto_delete_seconds: Optional[int] = None
    text_payload = command_arg
    if src is not None and command_arg:
        parsed = _parse_duration(command_arg)
        if parsed is not None:
            auto_delete_seconds = parsed
            text_payload = ""  # unused when replying, kept empty for clarity
        # If it doesn't parse as a duration, it's simply ignored (same as
        # the previous behaviour, where trailing args were unused in reply mode).

    if src is None and not command_arg:
        await bot.send_message(message.chat.id, _usage_text(), parse_mode=ParseMode.HTML)
        return
    if forward and src is None:
        await bot.send_message(
            message.chat.id,
            "Forward broadcast requires a <b>reply</b> to the message to forward.",
            parse_mode=ParseMode.HTML,
        )
        return

    targets = _resolve_targets(target_kind)
    if not targets.ids:
        empty = {
            "user": "No users found for this broadcast.",
            "chat": "No chats found for this broadcast.",
            "all": "No users or chats found for this broadcast.",
        }.get(target_kind, "No targets found for this broadcast.")
        await bot.send_message(message.chat.id, empty)
        return

    broadcast_id = uuid4().hex[:10]
    job = BroadcastJob(id=broadcast_id, initiator_id=message.from_user.id, auto_delete_seconds=auto_delete_seconds)
    _JOBS[broadcast_id] = job
    delete_markup = _delete_button(broadcast_id)

    status = await bot.send_message(
        message.chat.id,
        _start_message(targets, target_kind, forward=forward, auto_delete_seconds=auto_delete_seconds),
        parse_mode=ParseMode.HTML,
        reply_markup=delete_markup,
    )

    ok = 0
    failed = 0
    failed_ids: List[int] = []
    try:
        for target_id in targets.ids:
            message_id = await _send_to_target(bot, target_id, src, text_payload, forward=forward)
            if message_id is not None:
                ok += 1
                job.sent.append((target_id, message_id))
            else:
                failed += 1
                if len(failed_ids) < 10:
                    failed_ids.append(target_id)
            await asyncio.sleep(0.035)
    finally:
        action = "broadcast_%s" % target_kind
        if forward:
            action += "_forward"
        schedule_audit_telegram(
            "broadcast_completed",
            action=action,
            actor=format_user(message.from_user),
            target_kind=target_kind,
            user_targets=targets.user_count,
            chat_targets=targets.chat_count,
            total_targets=len(targets.ids),
            success=ok,
            failed=failed,
            via_reply=bool(src is not None),
            forward=forward,
            auto_delete_seconds=auto_delete_seconds,
            broadcast_id=broadcast_id,
        )

        summary = _complete_message(
            targets,
            target_kind,
            forward=forward,
            ok=ok,
            failed=failed,
            failed_ids=failed_ids,
            auto_delete_seconds=auto_delete_seconds,
        )
        # The Delete Broadcast button stays attached to the final summary too,
        # so an operator can wipe the run at any point, temp or not.
        try:
            await bot.edit_message_text(
                summary,
                chat_id=status.chat.id,
                message_id=status.message_id,
                parse_mode=ParseMode.HTML,
                reply_markup=delete_markup,
            )
        except Exception:
            status = await bot.send_message(
                message.chat.id, summary, parse_mode=ParseMode.HTML, reply_markup=delete_markup
            )

        if auto_delete_seconds:
            job.delete_task = asyncio.create_task(
                _schedule_auto_delete(bot, job, auto_delete_seconds, status.chat.id, status.message_id)
            )


# =============================================================================
# Commands — Copy (default)
# =============================================================================
@router.message(Command("broadcast_all", "broadcast"))
async def cmd_broadcast_all(message: Message, bot: Bot) -> None:
    await _run_broadcast(message, bot, "all", forward=False)


@router.message(Command("broadcast_users", "broadcast_user"))
async def cmd_broadcast_users(message: Message, bot: Bot) -> None:
    await _run_broadcast(message, bot, "user", forward=False)


@router.message(Command("broadcast_chats", "broadcast_chat"))
async def cmd_broadcast_chats(message: Message, bot: Bot) -> None:
    await _run_broadcast(message, bot, "chat", forward=False)


# =============================================================================
# Commands — Forward
# =============================================================================
@router.message(Command("broadcast_all_forward"))
async def cmd_broadcast_all_forward(message: Message, bot: Bot) -> None:
    await _run_broadcast(message, bot, "all", forward=True)


@router.message(Command("broadcast_users_forward"))
async def cmd_broadcast_users_forward(message: Message, bot: Bot) -> None:
    await _run_broadcast(message, bot, "user", forward=True)


@router.message(Command("broadcast_chats_forward"))
async def cmd_broadcast_chats_forward(message: Message, bot: Bot) -> None:
    await _run_broadcast(message, bot, "chat", forward=True)