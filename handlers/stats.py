# -*- coding: utf-8 -*-
"""Stats hub: /mystats, leaderboards, points, history, ss| callbacks."""

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from typing import Optional

from ui.inline_buttons import btn_callback, markup
from internationalization import _
from services import leaderboard_service, stats_service, user_service
from tg.helpers import answer_callback_query_safe, safe_edit_message_text, send_message
from ui.text_style import menu_title_bar, smallcaps

router = Router(name="stats")


def _hub_keyboard():
    return markup(
        [
            [
                btn_callback(smallcaps(_("My stats")), "ss|home", "primary", icon_role="p10"),
                btn_callback(smallcaps(_("Points")), "ss|pts", "success", icon_role="p11"),
            ],
            [
                btn_callback(smallcaps(_("Global stats")), "ss|lbg", "success", icon_role="p18"),
                btn_callback(smallcaps(_("Current group")), "ss|lbc", "danger", icon_role="p19"),
            ],
            [
                btn_callback(smallcaps(_("Weekly")), "ss|lb|w", "default", icon_role="p13"),
                btn_callback(smallcaps(_("Monthly")), "ss|lb|m", "default", icon_role="p14"),
            ],
            [
                btn_callback(smallcaps(_("Season")), "ss|lb|s", "default", icon_role="p15"),
            ],
            [btn_callback(smallcaps(_("History")), "ss|hist", "default", icon_role="p16")],
            [
                btn_callback(smallcaps(_("« Main menu")), "m|0", "default", icon_role="p17"),
            ],
        ]
    )


def _leaderboard_body(scope: str) -> str:
    if scope == "w":
        head = menu_title_bar("📅", _("Weekly leaderboard"))
        rows = leaderboard_service.top_weekly(10)
        key = "weekly_points"
    elif scope == "m":
        head = menu_title_bar("📆", _("Monthly leaderboard"))
        rows = leaderboard_service.top_monthly(10)
        key = "monthly_points"
    elif scope == "s":
        head = menu_title_bar("✨", _("Season leaderboard"))
        rows = leaderboard_service.top_season(10)
        key = "season_points"
    else:
        head = menu_title_bar("✦", _("All-time leaderboard"))
        rows = leaderboard_service.top_total(10)
        key = "total_points"
    body = leaderboard_service.format_leaderboard_rows(rows, key)
    return "%s\n\n%s" % (head, body)


def _global_stats_body() -> str:
    head = menu_title_bar("🌍", _("Global stats leaderboard"))
    rows = leaderboard_service.top_global_points(10)
    body = leaderboard_service.format_leaderboard_rows(rows, "total_points")
    return "%s\n\n%s" % (head, body)


def _current_group_stats_body(chat_id: Optional[int]) -> str:
    if chat_id is None:
        return "%s\n\n%s" % (
            menu_title_bar("🏟️", _("Current group leaderboard")),
            _("Open this leaderboard inside a group chat to view current group stats."),
        )
    head = menu_title_bar("🏟️", _("Current group leaderboard"))
    rows = leaderboard_service.top_chat_points(chat_id, 10)
    body = leaderboard_service.format_leaderboard_rows(rows, "total_points")
    return "%s\n\n%s" % (head, body)


@router.message(Command("mystats"))
async def cmd_mystats(message: Message, bot) -> None:
    user = message.from_user
    user_service.sync_telegram_profile(user)
    body = stats_service.format_mystats_html(user.id)
    text = "%s\n\n%s" % (menu_title_bar("📊", _("Your statistics")), body)
    await send_message(
        bot,
        message.chat.id,
        text=text,
        parse_mode=ParseMode.HTML,
        reply_markup=_hub_keyboard(),
    )


@router.message(Command("points"))
async def cmd_points(message: Message, bot) -> None:
    user = message.from_user
    user_service.sync_telegram_profile(user)
    text = stats_service.format_points_detail_html(user.id)
    await send_message(
        bot,
        message.chat.id,
        text=text,
        parse_mode=ParseMode.HTML,
        reply_markup=_hub_keyboard(),
    )


@router.message(Command("history"))
async def cmd_history(message: Message, bot) -> None:
    user = message.from_user
    body = stats_service.format_match_history_html(user.id)
    text = "%s\n\n%s" % (menu_title_bar("📜", _("Recent matches")), body)
    await send_message(
        bot,
        message.chat.id,
        text=text,
        parse_mode=ParseMode.HTML,
        reply_markup=_hub_keyboard(),
    )


@router.message(Command("leaderboard"))
async def cmd_leaderboard(message: Message, bot) -> None:
    text = _global_stats_body()
    await send_message(
        bot,
        message.chat.id,
        text=text,
        parse_mode=ParseMode.HTML,
        reply_markup=_hub_keyboard(),
    )


@router.message(Command("weeklylb"))
async def cmd_weeklylb(message: Message, bot) -> None:
    text = _leaderboard_body("w")
    await send_message(
        bot,
        message.chat.id,
        text=text,
        parse_mode=ParseMode.HTML,
        reply_markup=_hub_keyboard(),
    )


@router.message(Command("monthlylb"))
async def cmd_monthlylb(message: Message, bot) -> None:
    text = _leaderboard_body("m")
    await send_message(
        bot,
        message.chat.id,
        text=text,
        parse_mode=ParseMode.HTML,
        reply_markup=_hub_keyboard(),
    )


@router.message(Command("seasonlb"))
async def cmd_seasonlb(message: Message, bot) -> None:
    text = _leaderboard_body("s")
    await send_message(
        bot,
        message.chat.id,
        text=text,
        parse_mode=ParseMode.HTML,
        reply_markup=_hub_keyboard(),
    )


@router.callback_query(F.data.startswith("ss|"))
async def stats_hub_callback(query: CallbackQuery, bot) -> None:
    user = query.from_user
    data = query.data or ""
    await answer_callback_query_safe(query)
    user_service.sync_telegram_profile(user)

    parts = data.split("|")
    if len(parts) < 2:
        return

    action = parts[1]

    if action == "home":
        body = stats_service.format_mystats_html(user.id)
        await safe_edit_message_text(
            query,
            "%s\n\n%s" % (menu_title_bar("📊", _("Your statistics")), body),
            _hub_keyboard(),
        )
        return

    if action == "pts":
        await safe_edit_message_text(
            query,
            stats_service.format_points_detail_html(user.id),
            _hub_keyboard(),
        )
        return

    if action == "lb" and len(parts) >= 3:
        scope = parts[2]
        await safe_edit_message_text(query, _leaderboard_body(scope), _hub_keyboard())
        return

    if action == "lbg":
        await safe_edit_message_text(query, _global_stats_body(), _hub_keyboard())
        return

    if action == "lbc":
        chat_id = query.message.chat.id if query.message and query.message.chat else None
        await safe_edit_message_text(
            query,
            _current_group_stats_body(chat_id),
            _hub_keyboard(),
        )
        return

    if action == "hist":
        body = stats_service.format_match_history_html(user.id)
        await safe_edit_message_text(
            query,
            "%s\n\n%s" % (menu_title_bar("📜", _("Recent matches")), body),
            _hub_keyboard(),
        )
        return
