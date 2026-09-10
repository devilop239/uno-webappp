# -*- coding: utf-8 -*-
"""Private 1v1 friendly battle commands and callbacks."""

from __future__ import annotations

from aiogram import F, Bot, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

import deck.card as c
from ui.inline_buttons import btn_callback, btn_switch_query, btn_url, markup
from internationalization import _
from loggers import format_chat, format_user, schedule_audit_telegram
from services import user_service
from services.private_battle_service import CB_PREFIX, board_text, private_battles
from tg.helpers import answer_callback_query_safe
from ui.text_style import smallcaps
from utils import display_name_html

router = Router(name="private_mode")


def _play_surface_hint(bot_username: str) -> str:
    u = (bot_username or "unor0bot").lstrip("@")
    return _(
        "This private match is played via inline only.\n"
        "Open your friend/private chat and type: @{bot}\n"
        "Bot DM is for setup/lobby only."
    ).format(bot=u)


async def _safe_edit_or_send(bot: Bot, user_id: int, message_id: int | None, text: str, kb):
    if message_id:
        try:
            await bot.edit_message_text(
                chat_id=user_id,
                message_id=message_id,
                text=text,
                parse_mode=ParseMode.HTML,
                reply_markup=kb,
                disable_web_page_preview=True,
            )
            return message_id
        except Exception:
            pass
    msg = await bot.send_message(
        user_id,
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=kb,
        disable_web_page_preview=True,
    )
    return msg.message_id


def _board_kb(game, uid: int):
    if game.status == "pending_start":
        row = []
        if uid == game.player1_id:
            row.append(btn_callback(smallcaps(_("Start match")), f"{CB_PREFIX}|start_match|{game.game_id}", "success", icon_role="p6"))
        else:
            row.append(btn_callback(smallcaps(_("Waiting host start")), f"{CB_PREFIX}|noop", "primary", icon_role="p6"))
        row.append(btn_callback(smallcaps(_("Refresh")), f"{CB_PREFIX}|refresh|{game.game_id}", "primary", icon_role="p12"))
        return markup([row])
    if game.status != "active":
        return markup([[btn_callback(smallcaps(_("Closed")), f"{CB_PREFIX}|noop", "danger", icon_role="p6")]])
    return markup(
        [
            [btn_switch_query(smallcaps(_("Play via @bot")), "", "success")],
            [
                btn_callback(smallcaps(_("Refresh")), f"{CB_PREFIX}|refresh|{game.game_id}", "primary", icon_role="p12"),
                btn_callback(smallcaps(_("Leave match")), f"{CB_PREFIX}|leave_match|{game.game_id}", "danger", icon_role="p18"),
            ],
        ]
    )


def _hand_kb(game, uid: int, page: int):
    hand = game.hands.get(uid, [])
    playable = set(id(x) for x in private_battles.playable_hand(game, uid))
    page_size = 8
    start = max(0, page) * page_size
    items = hand[start:start + page_size]
    rows = []
    for i, card in enumerate(items, start=start):
        can = (uid == game.current_turn_user_id and game.choosing_color_for is None and id(card) in playable)
        flavor = "success" if can else "default"
        rows.append([btn_callback(
            "%s %s" % ("✅" if can else "•", repr(card)),
            f"{CB_PREFIX}|play|{game.game_id}|{game.turn_token}|{i}",
            flavor,
            icon_role="p13",
        )])
    nav = []
    if start > 0:
        nav.append(btn_callback("«", f"{CB_PREFIX}|hand|{game.game_id}|{game.turn_token}|{page - 1}", "primary", icon_role="p14"))
    if start + page_size < len(hand):
        nav.append(btn_callback("»", f"{CB_PREFIX}|hand|{game.game_id}|{game.turn_token}|{page + 1}", "primary", icon_role="p15"))
    if nav:
        rows.append(nav)
    rows.append([btn_callback(smallcaps(_("Back to board")), f"{CB_PREFIX}|refresh|{game.game_id}", "danger", icon_role="p16")])
    return markup(rows)


async def _sync_boards(bot: Bot, game, actor_id: int | None = None):
    for uid in game.players:
        opp = game.opponent(uid)
        viewer_name = "You"
        opp_name = "Opponent"
        if actor_id is not None and uid != actor_id:
            opp_name = display_name_html(type("x", (), {"first_name": "Opponent", "last_name": "", "username": ""})())
        text = board_text(game, uid, viewer_name, opp_name)
        mid = game.board_message_ids.get(uid)
        new_mid = await _safe_edit_or_send(bot, uid, mid, text, _board_kb(game, uid))
        game.board_message_ids[uid] = new_mid
    if game.status == "completed":
        winner = game.winner_user_id
        for uid in game.players:
            msg = _("You won the private battle!") if uid == winner else _("You lost the private battle.")
            await bot.send_message(uid, "<b>%s</b>" % smallcaps(msg), parse_mode=ParseMode.HTML)


async def sync_private_boards(bot: Bot, game, actor_id: int | None = None):
    await _sync_boards(bot, game, actor_id=actor_id)


async def _close_private_battle_for_user(bot: Bot, uid: int, chat=None, actor=None) -> bool:
    """
    Close active/pending private battle for a participant.
    Returns True when something was closed/cancelled; False when no target exists.
    """
    game = private_battles.game_for_user(uid)
    if game is None:
        # Keep /cancel behaviour friendly for hosts who still have a pending lobby.
        ok = await private_battles.cancel_lobby(uid)
        if ok:
            if actor is not None:
                schedule_audit_telegram(
                    "private_lobby_cancel",
                    action="private_lobby_cancel_alias",
                    user=format_user(actor),
                    chat=format_chat(chat),
                    ok=True,
                )
            await bot.send_message(uid, _("Lobby cancelled."))
            return True
        return False

    opponent_id = game.opponent(uid)
    await private_battles.close_game(game.game_id, reason="cancelled_by_user")
    await _sync_boards(bot, game, actor_id=uid)

    if actor is not None:
        schedule_audit_telegram(
            "private_match_cancelled",
            action="private_match_cancel",
            user=format_user(actor),
            chat=format_chat(chat),
            game_id=game.game_id,
            players=[game.player1_id, game.player2_id],
            cancelled_by=uid,
        )

    await bot.send_message(uid, _("You left the private battle. Match closed."))
    await bot.send_message(opponent_id, _("Opponent left the private battle. Match closed."))
    return True


@router.message(Command("privatenew"))
async def cmd_private_new(message: Message, bot: Bot) -> None:
    if message.chat.type != "private":
        await bot.send_message(message.chat.id, _("Use /privatenew in private chat with the bot."))
        return
    if not user_service.has_started_bot_in_dm(message.from_user.id):
        await bot.send_message(message.chat.id, _("Please start the bot in DM first with /start."))
        return
    host_name = display_name_html(message.from_user)
    lob, err = await private_battles.create_lobby(message.from_user.id, host_name)
    if err:
        await bot.send_message(message.chat.id, err)
        return
    schedule_audit_telegram(
        "private_lobby_created",
        action="private_lobby_create",
        user=format_user(message.from_user),
        chat=format_chat(message.chat),
        code=lob.code,
        status=lob.status,
    )
    bot_u = (await bot.get_me()).username or "unor0bot"
    link = "https://t.me/%s" % bot_u
    text = (
        '<tg-emoji emoji-id="6314575950688293716">🎯</tg-emoji> <b>%s</b>\n\n'
        "%s <code>%s</code>\n"
        "%s\n"
        "%s"
        % (
            smallcaps(_("Private lobby created")),
            smallcaps(_("Code:")),
            lob.code,
            smallcaps(_("Share this code with your friend and ask them to use /joincode.")),
            smallcaps(_("Waiting for opponent...")),
        )
    )
    kb = markup([[btn_url(smallcaps(_("Open bot")), link, "success", icon_role="p17")], [btn_callback(smallcaps(_("Cancel lobby")), "pv|cancel_lobby", "danger", icon_role="p18")]])
    await bot.send_message(message.chat.id, text, parse_mode=ParseMode.HTML, reply_markup=kb, disable_web_page_preview=True)


@router.message(Command("joincode"))
async def cmd_join_code(message: Message, bot: Bot) -> None:
    if message.chat.type != "private":
        await bot.send_message(message.chat.id, _("Use /joincode in private chat with the bot."))
        return
    if not user_service.has_started_bot_in_dm(message.from_user.id):
        await bot.send_message(message.chat.id, _("Please start the bot in DM first with /start."))
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await bot.send_message(message.chat.id, _("Usage: /joincode ABC123"))
        return
    game, err = await private_battles.join_by_code(parts[1], message.from_user.id)
    if err:
        await bot.send_message(message.chat.id, err)
        return
    schedule_audit_telegram(
        "private_lobby_joined",
        action="private_lobby_join",
        user=format_user(message.from_user),
        chat=format_chat(message.chat),
        game_id=game.game_id,
        players=[game.player1_id, game.player2_id],
        status=game.status,
    )
    me = await bot.get_me()
    await bot.send_message(
        game.player1_id,
        "<b>%s</b>\n%s"
        % (
            smallcaps(_("Opponent joined. Use /start_match or tap Start Match.")),
            smallcaps(_play_surface_hint(me.username or "unor0bot")),
        ),
        parse_mode=ParseMode.HTML,
    )
    await bot.send_message(
        game.player2_id,
        "<b>%s</b>\n%s"
        % (
            smallcaps(_("Joined successfully. Waiting for host to start.")),
            smallcaps(_play_surface_hint(me.username or "unor0bot")),
        ),
        parse_mode=ParseMode.HTML,
    )
    await _sync_boards(bot, game, actor_id=message.from_user.id)


@router.message(Command("cancelprivate"))
async def cmd_cancel_private(message: Message, bot: Bot) -> None:
    if message.chat.type != "private":
        return
    ok = await private_battles.cancel_lobby(message.from_user.id)
    schedule_audit_telegram(
        "private_lobby_cancel",
        action="private_lobby_cancel",
        user=format_user(message.from_user),
        chat=format_chat(message.chat),
        ok=bool(ok),
    )
    await bot.send_message(message.chat.id, _("Lobby cancelled.") if ok else _("No pending private lobby found."))


@router.message(F.chat.type == "private", Command("kill_private", "cancel_private", "cancel", "leave"))
async def cmd_private_leave_or_cancel(message: Message, bot: Bot) -> None:
    ok = await _close_private_battle_for_user(
        bot,
        message.from_user.id,
        chat=message.chat,
        actor=message.from_user,
    )
    if not ok:
        await bot.send_message(message.chat.id, _("No active private battle found."))


@router.message(Command("start_match", "start_game"))
async def cmd_start_match(message: Message, bot: Bot) -> None:
    if message.chat.type != "private":
        await bot.send_message(message.chat.id, _("Use this command in private chat."))
        return
    game = private_battles.game_for_user(message.from_user.id)
    if not game:
        await bot.send_message(message.chat.id, _("No active private battle found."))
        return
    ok, err = await private_battles.start_match(game.game_id, message.from_user.id)
    if not ok:
        await bot.send_message(message.chat.id, err)
        return
    schedule_audit_telegram(
        "private_match_started",
        action="private_match_start",
        user=format_user(message.from_user),
        chat=format_chat(message.chat),
        game_id=game.game_id,
        players=[game.player1_id, game.player2_id],
        turn_user_id=game.current_turn_user_id,
    )
    me = await bot.get_me()
    hint = "<b>%s</b>\n%s" % (
        smallcaps(_("Match started")),
        smallcaps(_play_surface_hint(me.username or "unor0bot")),
    )
    await bot.send_message(game.player1_id, hint, parse_mode=ParseMode.HTML)
    await bot.send_message(game.player2_id, hint, parse_mode=ParseMode.HTML)
    await _sync_boards(bot, game, actor_id=message.from_user.id)


@router.callback_query(F.data.startswith(f"{CB_PREFIX}|"))
async def private_callbacks(query: CallbackQuery, bot: Bot) -> None:
    await answer_callback_query_safe(query)
    uid = query.from_user.id
    data = (query.data or "").split("|")
    if len(data) < 2:
        return
    action = data[1]
    if action == "noop":
        return
    if action == "cancel_lobby":
        ok = await private_battles.cancel_lobby(uid)
        await bot.send_message(uid, _("Lobby cancelled.") if ok else _("No pending private lobby found."))
        return
    game = private_battles.game_for_user(uid)
    if not game:
        await bot.send_message(uid, _("No active private battle found."))
        return
    if action == "refresh":
        await _sync_boards(bot, game)
        return
    if action == "leave_match":
        ok = await _close_private_battle_for_user(
            bot,
            uid,
            chat=query.message.chat if query.message else None,
            actor=query.from_user,
        )
        if not ok:
            await bot.send_message(uid, _("No active private battle found."))
        return
    if action in ("hand", "draw", "play", "color"):
        me = await bot.get_me()
        await bot.send_message(
            uid,
            "<b>%s</b>\n%s"
            % (
                smallcaps(_("Play is blocked in bot DM")),
                smallcaps(_play_surface_hint(me.username or "unor0bot")),
            ),
            parse_mode=ParseMode.HTML,
        )
        return
    if action == "start_match":
        ok, err = await private_battles.start_match(game.game_id, uid)
        if not ok:
            await bot.send_message(uid, err)
            return
        schedule_audit_telegram(
            "private_match_started",
            action="private_match_start_callback",
            user=format_user(query.from_user),
            chat=format_chat(query.message.chat if query.message else None),
            game_id=game.game_id,
            players=[game.player1_id, game.player2_id],
            turn_user_id=game.current_turn_user_id,
        )
        me = await bot.get_me()
        hint = "<b>%s</b>\n%s" % (
            smallcaps(_("Match started")),
            smallcaps(_play_surface_hint(me.username or "unor0bot")),
        )
        await bot.send_message(game.player1_id, hint, parse_mode=ParseMode.HTML)
        await bot.send_message(game.player2_id, hint, parse_mode=ParseMode.HTML)
        await _sync_boards(bot, game, actor_id=uid)
        return


