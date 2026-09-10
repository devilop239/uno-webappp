# -*- coding: utf-8 -*-
"""Group game commands (formerly bot.py)."""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime

from aiogram import Bot, Router
from aiogram.enums import ParseMode
from aiogram import F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

import deck.card as c
from deck.styles import (
    ALT_DECK_STYLES,
    DECK_STYLE_ANIME,
    DECK_STYLE_NORMAL,
    DECK_STYLE_POKEMON,
    deck_style_selectable_for_mode,
    normalize_deck_style,
)
from core.actions import (
    cancel_fast_countdown,
    do_call_bluff,
    do_draw,
    do_play_card,
    do_skip,
    reset_waiting_time,
    start_player_countdown,
)
from config import ABANDON_PENALTY, DEFAULT_GAMEMODE, DM_START_BOT_USERNAME, MIN_PLAYERS
from errors import (
    AlreadyJoinedError,
    DeckEmptyError,
    LobbyClosedError,
    NoGameInChatError,
    NotEnoughPlayersError,
)
from handlers.menus import send_private_menu
from loggers import format_chat, format_user, players_snapshot, schedule_audit_telegram
from ui.inline_buttons import btn_callback, btn_switch_current_chat, btn_url, markup
from internationalization import _, __
from internationalization import pop_locale_stack_n, push_game_locales_for_user_chat
from services import user_service
from services.match_result_service import (
    capture_match_context,
    send_post_match_scoreboard,
)
from shared_vars import gm
from tg.helpers import (
    answer_callback_query_safe,
    delete_game_turn_prompt_safe,
    get_bot_username,
    safe_edit_message_text,
    send_game_turn_prompt,
    send_message,
    send_sticker,
    user_is_admin_aiogram,
    user_is_creator_or_admin_aiogram,
)
from utils import display_name, display_name_html, game_is_running
from ui.text_style import smallcaps

logger = logging.getLogger(__name__)

router = Router(name="game")

TEAM_CB_PREFIX = "tm|"
TEAM_REMATCH_PREFIX = "tmr|"
TEAM_REMATCH_TTL_SEC = 20 * 60
# Distinct from in-game NO MERCY callbacks (nm|…) so /new mode picks are not swallowed.
NEW_MODE_PREFIX = "ng|"
LOBBY_PREFIX = "lb|"
NEW_MODE_TTL_SEC = 10 * 60
TEAM_MODE_PICKER_TEXT = (
    '<tg-emoji emoji-id="6314237464315696206">✨</tg-emoji> <b>ᴛᴇᴀᴍ ᴜɴᴏ ʟᴏʙʙʏ</b>\n\n'
    '<tg-emoji emoji-id="6314575950688293716">🎯</tg-emoji> <b>ᴄʜᴏᴏsᴇ ʏᴏᴜʀ ʙᴀᴛᴛʟᴇ sᴛʏʟᴇ</b>\n\n'
    '<tg-emoji emoji-id="6311849260635656729">⚔️</tg-emoji> '
    "ᴘɪᴄᴋ ᴀ ᴍᴏᴅᴇ ғʀᴏᴍ ᴛʜᴇ ʙᴜᴛᴛᴏɴs ʙᴇʟᴏᴡ ᴀɴᴅ ʟᴇᴛ ᴛʜᴇ ᴛᴇᴀᴍ ᴍᴀᴛᴄʜ ʙᴇɢɪɴ."
)


async def _dm_start_required_guard(message: Message, bot: Bot) -> bool:
    """
    Return True when command should be blocked (user has not started bot in DM).
    """
    if message.chat.type not in ("group", "supergroup"):
        return False
    user = message.from_user
    if user is None:
        return False
    if user_service.has_started_bot_in_dm(user.id):
        return False
    bot_username = (DM_START_BOT_USERNAME or "").strip().lstrip("@")
    if not bot_username:
        bot_username = (await get_bot_username(bot)).lstrip("@")
    start_url = "https://t.me/%s?start=setup" % bot_username
    await send_message(
        bot,
        message.chat.id,
        text=_("You need to start me in private before creating or joining a game."),
        reply_to_message_id=message.message_id,
        reply_markup=markup(
            [[btn_url(_("Start Bot"), start_url, "primary", icon_role="p6")]]
        ),
    )
    return True


def _team_title(game, team_id: str) -> str:
    t = game.team_names.get(team_id, "").strip()
    return t or ("Team Inferno" if team_id == "A" else "Team Frost")


def _team_players_line(game, team_id: str) -> str:
    names = []
    by_uid = {int(p.user.id): p for p in game.players}
    for uid in game.team_members.get(team_id, []):
        p = by_uid.get(int(uid))
        if p:
            names.append(display_name_html(p.user))
    if not names:
        return "—"
    return ", ".join(names)


def _team_lobby_text(game) -> str:
    mode_label = "%dv%d" % (game.team_size, game.team_size)
    method = "Manual" if game.team_assignment == "manual" else "Random"
    return (
        "<b>%s</b>\n\n"
        "A: <b>%s</b> (%d/%d)\n%s\n\n"
        "B: <b>%s</b> (%d/%d)\n%s\n\n"
        "%s"
        % (
            smallcaps("TEAM UNO %s (%s)" % (mode_label, method)),
            _team_title(game, "A"),
            len(game.team_members["A"]),
            game.team_size,
            _team_players_line(game, "A"),
            _team_title(game, "B"),
            len(game.team_members["B"]),
            game.team_size,
            _team_players_line(game, "B"),
            smallcaps("Use buttons to join/switch teams. Start unlocks when both sides are full."),
        )
    )


def _team_lobby_keyboard(game):
    rows = []
    if game.team_assignment == "manual":
        rows.append(
            [
                btn_callback("Join A", TEAM_CB_PREFIX + "join|A", "primary", "p1"),
                btn_callback("Join B", TEAM_CB_PREFIX + "join|B", "primary", "p2"),
            ]
        )
    else:
        rows.append([btn_callback("Join Team Lobby", TEAM_CB_PREFIX + "join|R", "primary", "p3")])
    rows.append([btn_callback("Leave", TEAM_CB_PREFIX + "leave", "danger", "p4")])
    gid = getattr(game, "match_uuid", "")
    rows.append(
        [
            btn_callback(
                "ᴄᴀɴᴄᴇʟ ʟᴏʙʙʏ",
                f"{TEAM_CB_PREFIX}cancel_lobby|{gid}",
                "danger",
                "p_clb",
            )
        ]
    )
    rows.append([btn_callback("Change Mode", TEAM_CB_PREFIX + "change_mode", "default", "p12")])
    rows.append([btn_callback("Start Team Match", TEAM_CB_PREFIX + "start", "success", "p5")])
    return markup(rows)


def _team_mode_picker_keyboard():
    return markup(
        [
            [
                {
                    "text": smallcaps("2v2 Manual"),
                    "callback_data": TEAM_CB_PREFIX + "mode|2|manual",
                    "style": "primary",
                    "icon_custom_emoji_id": "5327904525506327345",
                },
                {
                    "text": smallcaps("2v2 Random"),
                    "callback_data": TEAM_CB_PREFIX + "mode|2|random",
                    "style": "success",
                    "icon_custom_emoji_id": "5325971455215680945",
                },
            ],
            [
                {
                    "text": smallcaps("3v3 Manual"),
                    "callback_data": TEAM_CB_PREFIX + "mode|3|manual",
                    "style": "primary",
                    "icon_custom_emoji_id": "5327948037820004176",
                },
                {
                    "text": smallcaps("3v3 Random"),
                    "callback_data": TEAM_CB_PREFIX + "mode|3|random",
                    "style": "success",
                    "icon_custom_emoji_id": "5328295947350848665",
                },
            ],
            [
                btn_callback(
                    smallcaps("Cancel lobby"),
                    TEAM_CB_PREFIX + "cancel_lobby",
                    "danger",
                    "p_clb",
                )
            ],
        ]
    )


_pending_new_mode = {}


def _new_mode_selector_text() -> str:
    return (
        "<b>ᴄʜᴏᴏsᴇ ᴀ ɢᴀᴍᴇ ᴍᴏᴅᴇ</b>\n\n"
        "sᴇʟᴇᴄᴛ ᴏɴᴇ ᴏғ ᴛʜᴇ ᴍᴏᴅᴇs ʙᴇʟᴏᴡ ᴛᴏ ᴄʀᴇᴀᴛᴇ ʏᴏᴜʀ ʟᴏʙʙʏ."
    )


def _new_mode_keyboard(token: str):
    return markup(
        [
            [
                btn_callback("𝐂ʟᴀssɪᴄ", f"{NEW_MODE_PREFIX}pick|classic|{token}", "primary", "p1"),
                btn_callback("𝐒ᴀɴɪᴄ", f"{NEW_MODE_PREFIX}pick|fast|{token}", "success", "p2"),
            ],
            [
                btn_callback("𝐖ɪʟᴅ", f"{NEW_MODE_PREFIX}pick|wild|{token}", "primary", "wld"),
                btn_callback("𝐓ᴇxᴛ", f"{NEW_MODE_PREFIX}pick|text|{token}", "success", "p4"),
            ],
            [
                btn_callback("𝐑ᴀɪɴʙᴏᴡ", f"{NEW_MODE_PREFIX}pick|rainbow|{token}", "primary", "rbw"),
                btn_callback("𝐒ᴜᴅᴅᴇɴ 𝐃ᴇᴀᴛʜ", f"{NEW_MODE_PREFIX}pick|sudden_death|{token}", "success", "sdth"),
            ],
            [
                btn_callback(
                    "ɴᴏ ᴍᴇʀᴄʏ",
                    f"{NEW_MODE_PREFIX}pick|no_mercy|{token}",
                    "danger",
                    "p1",
                ),
            ],
            [
                btn_callback("𝐓ᴇᴀᴍ", f"{NEW_MODE_PREFIX}pick|team|{token}", "danger", "p5"),
            ],
        ]
    )


async def _is_lobby_owner_or_admin(
    query, game, bot
) -> bool:
    if (game.starter and
            query.from_user.id == game.starter.id):
        return True
    return await user_is_creator_or_admin_aiogram(
        query.from_user, game, bot, game.chat
    )


def _lobby_text(game):
    return (
        "<b>%s ʟᴏʙʙʏ ᴄʀᴇᴀᴛᴇᴅ</b>\n\n"
        "ᴊᴏɪɴ ᴜsɪɴɢ /join ᴏʀ ᴛᴀᴘ ᴊᴏɪɴ.\n"
        "ʜᴏsᴛ/ᴀᴅᴍɪɴ ᴄᴀɴ sᴛᴀʀᴛ ᴡɪᴛʜ /start ᴏʀ sᴛᴀʀᴛ."
    ) % _mode_label(game.mode)


def _lobby_controls_keyboard(game):
    gid = getattr(game, "match_uuid", "")
    return markup(
        [
            [btn_callback("ᴊᴏɪɴ", f"{LOBBY_PREFIX}join|{gid}", "success", "p6")],
            [
                btn_callback("sᴛᴀʀᴛ", f"{LOBBY_PREFIX}start|{gid}", "primary", "p7"),
                btn_callback("ᴄʟᴏsᴇ", f"{LOBBY_PREFIX}close|{gid}", "danger", "p8"),
            ],
            [
                btn_callback(
                    "ᴄᴀɴᴄᴇʟ ʟᴏʙʙʏ",
                    f"{LOBBY_PREFIX}cancel|{gid}",
                    "danger",
                    "p_clb",
                )
            ],
            [
                btn_callback(
                    "sᴇᴛᴛɪɴɢs",
                    "lb|settings",
                    "success",
                    "sttg_21",
                )
            ],
        ]
    )


def _cancel_lobby_success_html() -> str:
    return (
        "<b>ʟᴏʙʙʏ ᴄᴀɴᴄᴇʟʟᴇᴅ</b>\n\n"
        "<i>%s</i>"
        % smallcaps("Use /new to create a new lobby when you are ready.")
    )


async def _try_cancel_lobby(bot: Bot, chat, user, game):
    """
    Host/admin-only: remove an unstarted lobby so a new one can be created.
    Returns None on success, or: no_game, started, denied, failed.
    """
    if not game:
        return "no_game"
    if game.started:
        return "started"
    if not await user_is_creator_or_admin_aiogram(user, game, bot, chat):
        return "denied"
    if not gm.cancel_unstarted_lobby(chat):
        return "failed"
    return None


def _mode_label(mode: str) -> str:
    return {
        "classic": "🎻 ᴄʟᴀssɪᴄ",
        "fast": "🚀 sᴀɴɪᴄ",
        "wild": "🐉 ᴡɪʟᴅ",
        "rainbow": "🌈 ʀᴀɪɴʙᴏᴡ",
        "text": "✍️ ᴛᴇxᴛ",
        "sudden_death": "💀 sᴜᴅᴅᴇɴ ᴅᴇᴀᴛʜ",
        "no_mercy": "🔥 ɴᴏ ᴍᴇʀᴄʏ",
    }.get(mode, "🎻 ᴄʟᴀssɪᴄ")


def _status_deck_remaining(game) -> int:
    deck = getattr(game, "deck", None)
    if deck is None:
        return 0
    return len(getattr(deck, "cards", []) or [])


def _status_mode_line(game) -> str:
    if getattr(game, "is_team_mode", False):
        n = max(2, int(game.team_size or 2))
        assign = "ᴍᴀɴᴜᴀʟ" if game.team_assignment == "manual" else "ʀᴀɴᴅᴏᴍ"
        return (
            "🎯 <b>ᴍᴏᴅᴇ:</b>  %s — %dv%d <i>(%s)</i>"
            % (smallcaps("Team UNO"), n, n, assign)
        )
    return "🃏 <b>ᴍᴏᴅᴇ:</b>  %s" % (_mode_label(game.mode),)


def _status_round_line(game) -> str:
    if not game.started:
        return "🔄 <b>ʀᴏᴜɴᴅ:</b>  %s" % smallcaps("Lobby — waiting for /start")
    if (
        game.mode in ("sudden_death", "no_mercy")
        or getattr(game, "is_team_mode", False)
    ):
        rn = 1
    else:
        rn = max(1, int(getattr(game, "players_won", 0) or 0) + 1)
    return "🔄 <b>ʀᴏᴜɴᴅ:</b>  %s" % smallcaps("Round %d — In Progress" % rn)


def _status_settings_block(game, *, for_lobby: bool) -> str:
    rows = []
    if game.mode == "no_mercy":
        from no_mercy.deck_fill import estimated_deck_size

        n_players = max(len(game.players), 2)
        deck_n = estimated_deck_size(
            n_players, hand_size=game.effective_hand_size()
        )
        rows.append("  • %s  →  %s" % (smallcaps("Draw Stack"), smallcaps("ON (locked)")))
        rows.append("  • %s  →  %d" % (smallcaps("Hand Size"), game.effective_hand_size()))
        rows.append(
            "  • %s  →  %s (%d %s)"
            % (
                smallcaps("Deck"),
                smallcaps("NO MERCY"),
                deck_n,
                smallcaps("cards"),
            )
        )
        rows.append("  • %s  →  %s" % (smallcaps("Elimination"), smallcaps("30+ cards")))
    else:
        if game.stacking_enabled:
            rows.append("  • %s  →  ON" % smallcaps("Draw Stack"))
        rows.append("  • %s  →  %s" % (smallcaps("Deck Style"), smallcaps(game.deck_style_display())))
        hs = game.effective_hand_size()
        if hs != 7:
            rows.append("  • %s  →  %d" % (smallcaps("Hand Size"), hs))
    if getattr(game, "translate", False):
        rows.append("  • %s  →  ON" % smallcaps("Translation"))
    if for_lobby and not game.open:
        rows.append("  • %s  →  %s" % (smallcaps("Lobby"), smallcaps("Closed")))
    if not rows:
        return ""
    return "⚙️ <b>ꜱᴇᴛᴛɪɴɢꜱ:</b>\n" + "\n".join(rows)


def _build_status_snapshot_html(game) -> str:
    """Read-only HTML snapshot for /status (lobby or in progress)."""
    lines = [
        "╔══════════════════════════╗",
        "     🎮 <b>ɢᴀᴍᴇ ꜱᴛᴀᴛᴜꜱ</b>",
        "╚══════════════════════════╝",
        _status_mode_line(game),
        _status_round_line(game),
        "",
        "👥 <b>ᴘʟᴀʏᴇʀꜱ:</b>",
    ]
    players = list(game.players) if game.players else []
    if not players:
        lines.append("  • <i>%s</i>" % smallcaps("No players yet"))
    elif not game.started:
        for p in players:
            lines.append(
                "  • %s  →  —" % (display_name_html(p.user),)
            )
    else:
        for i, p in enumerate(players):
            n = len(p.cards or [])
            warn = " 🚨" if n == 1 else (" ⚠️" if n == 2 else "")
            cw = "card" if n == 1 else "cards"
            bullet = "➤" if i == 0 else "•"
            lines.append(
                "  %s  %s  →  %d %s%s"
                % (bullet, display_name_html(p.user), n, cw, warn)
            )

    if game.started and game.current_player:
        lines.append("")
        lines.append(
            "⏳ <b>ᴄᴜʀʀᴇɴᴛ ᴛᴜʀɴ:</b>  %s"
            % (display_name_html(game.current_player.user),)
        )
        lines.append(
            "📦 <b>ᴅᴇᴄᴋ:</b>  %d cards remaining" % _status_deck_remaining(game)
        )

    settings = _status_settings_block(game, for_lobby=not game.started)
    if settings:
        lines.append("")
        lines.append(settings)
    return "\n".join(lines)


def _hand_size_picker_text(game):
    current = game.effective_hand_size()
    return (
        "<blockquote>"
        "<tg-emoji emoji-id=\"5904258298764334001\">✨</tg-emoji> <b>ɢᴀᴍᴇ sᴇᴛᴛɪɴɢs</b>\n\n"
        "📋 <b>sᴛᴀʀᴛɪɴɢ ʜᴀɴᴅ sɪᴢᴇ</b>\n"
        "ᴄᴜʀʀᴇɴᴛ: <b>%d ᴄᴀʀᴅs</b> ᴘᴇʀ ᴘʟᴀʏᴇʀ\n\n"
        "sᴇʟᴇᴄᴛ ᴀ ʜᴀɴᴅ sɪᴢᴇ ʙᴇʟᴏᴡ ᴏʀ ᴜsᴇ\n"
        "<code>/handsize &lt;number&gt;</code> ɪɴ ᴄʜᴀᴛ."
        "</blockquote>"
    ) % current


def _hand_size_picker_keyboard(game):
    current = game.effective_hand_size()
    gid = getattr(game, "match_uuid", "")
    def style(n):
        return "success" if n == current else "default"
    return markup([
        [
            btn_callback("𝟽 ᴄᴀʀᴅs",  f"lb|hs|7|{gid}",  style(7),  "hs_7"),
        ],
        [
            btn_callback("𝟷𝟺 ᴄᴀʀᴅs", f"lb|hs|14|{gid}", style(14), "hs_14"),
        ],
        [
            btn_callback("𝟸𝟷 ᴄᴀʀᴅs", f"lb|hs|21|{gid}", style(21), "hs_21"),
        ],
        [
            btn_callback("ʙᴀᴄᴋ", f"lb|back|{gid}", "danger", "bck_21")
        ]
    ])


def _settings_main_text(game):
    return (
        " <b>ꜱᴇᴛᴛɪɴɢꜱ</b>\n\n"
        "Configure your game before starting.\n"
        "Tap a setting below to change it."
    )


def _settings_main_keyboard(game):
    hs = game.effective_hand_size()
    stack = "✅ ON" if game.stacking_enabled else "❌ OFF"
    deck = game.deck_style_display()
    return markup([
        [
            btn_callback(
                "ʜᴀɴᴅ ꜱɪᴢᴇ  —  %d ᴄᴀʀᴅꜱ" % hs,
                "lb|settings|handsize",
                "primary", "p1"
            ),
        ],
        [
            btn_callback(
                "ᴅᴇᴄᴋ ꜱᴛʏʟᴇ  —  %s" % deck,
                "lb|settings|deckstyle",
                "success", "deck"
            ),
        ],
        [
            btn_callback(
                "ᴅʀᴀᴡ ꜱᴛᴀᴄᴋ  —  %s" % stack,
                "lb|settings|drawstack",
                "danger", "p2"
            ),
        ],
        [
            btn_callback(
                "ʙᴀᴄᴋ ᴛᴏ ʟᴏʙʙʏ",
                "lb|back",
                "success", "bck_21"
            ),
        ],
    ])


def _handsize_text(game):
    return (
        "<tg-emoji emoji-id=\"5456140674028019486\">✨</tg-emoji> <b>ʜᴀɴᴅ ꜱɪᴢᴇ</b>\n\n"
        "ꜱᴇᴛꜱ ʜᴏᴡ ᴍᴀɴʏ ᴄᴀʀᴅꜱ ᴇᴀᴄʜ ᴘʟᴀʏᴇʀ ꜱᴛᴀʀᴛꜱ ᴡɪᴛʜ.\n"
        "ᴅᴇꜰᴀᴜʟᴛ ɪꜱ 7 — ʜɪɢʜᴇʀ ɴᴜᴍʙᴇʀꜱ ᴍᴇᴀɴ ʟᴏɴɢᴇʀ ɢᴀᴍᴇꜱ.\n\n"
        "<b>ᴍɪɴɪᴍᴜᴍ:</b> 7.\n"
        "<b>ᴏɴʟʏ ᴍᴜʟᴛɪᴘʟᴇꜱ ᴏꜰ 7 ᴀʀᴇ ᴀʟʟᴏᴡᴇᴅ</b>"
    )


def _handsize_keyboard(game):
    current = game.effective_hand_size()

    def _style(n):
        return "success" if n == current else "default"

    def _label(n):
        return (" %d" % n) if n == current else str(n)

    return markup([
        [
            btn_callback(_label(7), "lb|hs|7", _style(7), "hs_7"),
            btn_callback(_label(14), "lb|hs|14", _style(14), "hs_14"),
            btn_callback(_label(21), "lb|hs|21", _style(21), "hs_21"),
        ],
        [
            btn_callback(
                "ʙᴀᴄᴋ ᴛᴏ ꜱᴇᴛᴛɪɴɢꜱ",
                "lb|settings",
                "danger", "bck_21"
            ),
        ],
    ])


def _drawstack_text(game):
    return (
        "<tg-emoji emoji-id=\"5936130851635990622\">✨</tg-emoji> <b>ᴅʀᴀᴡ ꜱᴛᴀᴄᴋ</b>\n\n"
        "ᴡʜᴇɴ <b>ᴏɴ</b>, +4 ᴀɴᴅ +8 ᴄᴀʀᴅꜱ ᴄᴀɴ ʙᴇ ᴄᴏᴜɴᴛᴇʀᴇᴅ ᴡɪᴛʜ ᴀɴᴏᴛʜᴇʀ +4 ᴏʀ +8.\n\n"
        "<b>Examples:</b>\n"
        "• +4 → +4 = 8 ᴄᴀʀᴅꜱ\n"
        "• +4 → +8 = 12 ᴄᴀʀᴅꜱ\n"
        "• +8 → +8 = 16 ᴄᴀʀᴅꜱ\n\n"
        "<tg-emoji emoji-id=\"5994495149336434048\">✨</tg-emoji> ᴡᴏʀᴋꜱ ɪɴ ᴀʟʟ ᴍᴏᴅᴇꜱ.\n"
        "<tg-emoji emoji-id=\"5994495149336434048\">✨</tg-emoji> ʙʟᴜꜰꜰ ᴄʜᴀʟʟᴇɴɢᴇ ꜱᴛɪʟʟ ᴡᴏʀᴋꜱ."
    )


def _deckstyle_text(game):
    current = game.deck_style_display()
    rainbow_note = ""
    if game.mode == "rainbow":
        rainbow_note = (
            "\n\n<tg-emoji emoji-id=\"5994495149336434048\">✨</tg-emoji> "
            "<b>ʀᴀɪɴʙᴏᴡ ᴍᴏᴅᴇ:</b> ᴀɴɪᴍᴇ & ᴘᴏᴋᴇᴍᴏɴ ᴅᴇᴄᴋꜱ "
            "ᴀʀᴇ ɴᴏᴛ ᴀᴠᴀɪʟᴀʙʟᴇ ʏᴇᴛ — ɴᴏʀᴍᴀʟ ᴄᴀʀᴅꜱ ᴡɪʟʟ ʙᴇ ᴜꜱᴇᴅ."
        )
    return (
        "<tg-emoji emoji-id=\"5456140674028019486\">✨</tg-emoji> <b>ᴅᴇᴄᴋ ꜱᴛʏʟᴇ</b>\n\n"
        "ᴄʜᴏᴏꜱᴇ ᴡʜɪᴄʜ ᴄᴀʀᴅ ꜱᴛɪᴄᴋᴇʀ ᴘᴀᴄᴋ ᴛᴏ ᴜꜱᴇ.\n"
        "ᴄᴜʀʀᴇɴᴛ: <b>%s</b>\n\n"
        "<b>ɴᴏʀᴍᴀʟ</b> — ꜱᴛᴀɴᴅᴀʀᴅ ᴜɴᴏ ᴄᴀʀᴅꜱ\n"
        "<b>ᴀɴɪᴍᴇ</b> — ᴀɴɪᴍᴇ ᴄʜᴀʀᴀᴄᴛᴇʀ ᴄᴀʀᴅꜱ\n"
        "<b>ᴘᴏᴋᴇᴍᴏɴ</b> — ᴘᴏᴋᴇᴍᴏɴ ᴄᴀʀᴅꜱ"
        "%s"
    ) % (current, rainbow_note)


def _deckstyle_keyboard(game):
    effective = game.effective_deck_style()
    alt_ok = deck_style_selectable_for_mode(game.mode)

    def _style(choice: str) -> str:
        if choice in ALT_DECK_STYLES and not alt_ok:
            return "default"
        return "success" if effective == choice else "default"

    def _label(text: str, choice: str) -> str:
        if effective == choice and (choice not in ALT_DECK_STYLES or alt_ok):
            return " %s" % text
        return text

    return markup([
        [
            btn_callback(
                _label("ɴᴏʀᴍᴀʟ", DECK_STYLE_NORMAL),
                "lb|deck|normal",
                _style(DECK_STYLE_NORMAL),
                "nrml",
            ),
            btn_callback(
                _label("ᴀɴɪᴍᴇ", DECK_STYLE_ANIME),
                "lb|deck|anime",
                _style(DECK_STYLE_ANIME),
                "p4",
            ),
            btn_callback(
                _label("ᴘᴏᴋᴇᴍᴏɴ", DECK_STYLE_POKEMON),
                "lb|deck|pokemon",
                _style(DECK_STYLE_POKEMON),
                "p5",
            ),
        ],
        [
            btn_callback(
                "ʙᴀᴄᴋ ᴛᴏ ꜱᴇᴛᴛɪɴɢꜱ",
                "lb|settings",
                "danger", "bck_21"
            ),
        ],
    ])


def _drawstack_keyboard(game):
    on = game.stacking_enabled
    return markup([
        [
            btn_callback(
                "ᴏɴ" if on else "ᴏɴ",
                "lb|stack|on",
                "success" if on else "default", "p2"
            ),
            btn_callback(
                "ᴏꜰꜰ" if on else "ᴏꜰꜰ",
                "lb|stack|off",
                "default" if on else "success", "p2"
            ),
        ],
        [
            btn_callback(
                "ʙᴀᴄᴋ ᴛᴏ ꜱᴇᴛᴛɪɴɢꜱ",
                "lb|settings",
                "danger", "bck_21"
            ),
        ],
    ])


async def _send_team_mode_intro(bot: Bot, chat_id: int) -> None:
    await send_message(
        bot,
        chat_id,
        text=TEAM_MODE_PICKER_TEXT,
        parse_mode=ParseMode.HTML,
        reply_markup=_team_mode_picker_keyboard(),
    )


async def _create_lobby_for_mode(bot: Bot, chat, owner, mode: str):
    game = gm.new_game(chat)
    if game is None:
        return None
    game.starter = owner
    game.owner.add(owner.id)
    try:
        user_service.ensure_user_row(owner)
        user_service.sync_telegram_profile(owner)
    except Exception:
        logger.exception("user profile sync on mode-selected /new failed")
    if mode == "team":
        game.enable_team_mode(3, "manual")
        await _send_team_mode_intro(bot, chat.id)
        return game
    game.set_mode(mode)
    if mode == "no_mercy":
        from no_mercy import configure_new_lobby

        configure_new_lobby(game)
    await send_message(
        bot,
        chat.id,
        text=(
            "<b>%s ʟᴏʙʙʏ ᴄʀᴇᴀᴛᴇᴅ</b>\n\n"
            "ᴊᴏɪɴ ᴜsɪɴɢ /join ᴏʀ ᴛᴀᴘ ᴊᴏɪɴ.\n"
            "ʜᴏsᴛ/ᴀᴅᴍɪɴ ᴄᴀɴ sᴛᴀʀᴛ ᴡɪᴛʜ /start ᴏʀ sᴛᴀʀᴛ."
            + (
                "\n\n<i>🔥 Extreme rules · 7 cards · stacking ON · elimination at 30.</i>"
                if mode == "no_mercy"
                else ""
            )
        )
        % _mode_label(mode),
        parse_mode=ParseMode.HTML,
        reply_markup=_lobby_controls_keyboard(game),
    )
    return game


async def _join_active_lobby(bot: Bot, chat, user, reply_to_message_id=None):
    game = gm.get_active_game(chat.id)
    assigned_random_team = None
    if game and game.is_team_mode and not game.started:
        uid = user.id
        if game.team_assignment == "manual" and not game.team_of(uid):
            await send_message(
                bot,
                chat.id,
                text=_("Choose a team from the team lobby buttons first."),
                reply_to_message_id=reply_to_message_id,
            )
            return
        if game.team_assignment == "random" and not game.team_of(uid):
            if (
                len(game.team_members["A"]) <= len(game.team_members["B"])
                and len(game.team_members["A"]) < game.team_size
            ):
                game.team_members["A"].append(uid)
                assigned_random_team = "A"
            elif len(game.team_members["B"]) < game.team_size:
                game.team_members["B"].append(uid)
                assigned_random_team = "B"
            else:
                await send_message(bot, chat.id, text=_("Team lobby is full."))
                return
    elif game and game.is_team_mode and game.started:
        await send_message(
            bot,
            chat.id,
            text=_("Team games cannot be joined after start."),
            reply_to_message_id=reply_to_message_id,
        )
        return
    try:
        gm.join_game(user, chat)
    except LobbyClosedError:
        if assigned_random_team:
            game.leave_team_lobby(user.id)
        await send_message(bot, chat.id, text=_("The lobby is closed"))
    except NoGameInChatError:
        if assigned_random_team:
            game.leave_team_lobby(user.id)
        await send_message(
            bot,
            chat.id,
            text=_("ɴᴏ ɢᴀᴍᴇ ɪɴ ᴘʀᴏɢʀᴇꜱꜱ 🎮 ᴜꜱᴇ /new ᴛᴏ ꜱᴛᴀʀᴛ"),
            reply_to_message_id=reply_to_message_id,
        )
    except AlreadyJoinedError:
        if assigned_random_team:
            game.leave_team_lobby(user.id)
        await send_message(
            bot,
            chat.id,
            text=_("ʏᴏᴜ ᴀʟʀᴇᴀᴅʏ ᴊᴏɪɴᴇᴅ ᴛʜᴇ ɢᴀᴍᴇ. ꜱᴛᴀʀᴛ ᴛʜᴇ ɢᴀᴍᴇ ᴡɪᴛʜ /start"),
            reply_to_message_id=reply_to_message_id,
        )
    except DeckEmptyError:
        if assigned_random_team:
            game.leave_team_lobby(user.id)
        await send_message(
            bot,
            chat.id,
            text=_("ᴄᴀʀᴅꜱ ᴀʀᴇ ᴀʟᴍᴏꜱᴛ ɢᴏɴᴇ 😭 ᴄᴀɴ’ᴛ ᴀᴅᴅ ɴᴇᴡ ᴘʟᴀʏᴇʀꜱ"),
            reply_to_message_id=reply_to_message_id,
        )
    else:
        schedule_audit_telegram(
            "player_joined_lobby",
            action="join",
            user=format_user(user),
            chat=format_chat(chat),
        )
        await send_message(
            bot,
            chat.id,
            text=_("ᴊᴏɪɴᴇᴅ ᴛʜᴇ ɢᴀᴍᴇ"),
            reply_to_message_id=reply_to_message_id,
        )


@router.message(Command("status"))
async def status_command(message: Message, bot) -> None:
    """Read-only snapshot of lobby or running game (does not touch game state)."""
    if message.chat.type == "private":
        await send_private_menu(message, bot)
        return
    game = gm.get_active_game(message.chat.id)
    if not game:
        await send_message(
            bot,
            message.chat.id,
            text=(
                "❌ ɴᴏ ᴀᴄᴛɪᴠᴇ ɢᴀᴍᴇ ɪꜱ ʀᴜɴɴɪɴɢ ʀɪɢʜᴛ ɴᴏᴡ.\n"
                "🎮 ꜱᴛᴀʀᴛ ᴏɴᴇ ᴜꜱɪɴɢ /new"
            ),
            parse_mode=ParseMode.HTML,
        )
        return
    await send_message(
        bot,
        message.chat.id,
        text=_build_status_snapshot_html(game),
        parse_mode=ParseMode.HTML,
    )


@router.message(Command("notify_me"))
async def notify_me(message: Message, bot) -> None:
    chat_id = message.chat.id
    if message.chat.type == "private":
        bot_u = await get_bot_username(bot)
        await send_message(
            bot,
            chat_id,
            text=_(
                "Use this command in a group to get a DM when someone starts a new game there."
            ),
            reply_markup=markup(
                [
                    [
                        btn_url(
                            _("Add bot to a group"),
                            "https://t.me/%s?startgroup=1" % bot_u,
                            "success",
                        )
                    ]
                ]
            ),
        )
    else:
        try:
            gm.remind_dict[chat_id].add(message.from_user.id)
        except KeyError:
            gm.remind_dict[chat_id] = {message.from_user.id}


@router.message(Command("new"))
async def new_game(message: Message, bot) -> None:
    chat_id = message.chat.id
    if message.chat.type == "private":
        await send_private_menu(message, bot)
        return
    if await _dm_start_required_guard(message, bot):
        return

    if message.chat.id in gm.remind_dict:
        for uid in gm.remind_dict[message.chat.id]:
            await send_message(
                bot,
                uid,
                text=_("A new game has been started in {title}").format(
                    title=message.chat.title
                ),
            )
        del gm.remind_dict[message.chat.id]

    if gm.get_active_game(chat_id) is not None:
        existing = gm.get_active_game(chat_id)
        if existing and existing.started:
            await send_message(
                bot,
                chat_id,
                text=_(
                    "You can't create a new game right now. "
                    "A previous game is already in progress."
                ),
            )
        else:
            await send_message(
                bot,
                chat_id,
                text=_("A game lobby already exists in this chat."),
            )
        return

    token = uuid.uuid4().hex[:12]
    _pending_new_mode[chat_id] = {
        "token": token,
        "owner_id": message.from_user.id,
        "created_at": time.time(),
        "processed": False,
    }
    await send_message(
        bot,
        chat_id,
        text=_new_mode_selector_text(),
        parse_mode=ParseMode.HTML,
        reply_markup=_new_mode_keyboard(token),
    )


@router.message(Command("teamnew"))
async def team_new_game(message: Message, bot: Bot) -> None:
    if message.chat.type == "private":
        await send_private_menu(message, bot)
        return
    game = gm.new_game(message.chat)
    if game is None:
        await send_message(
            bot,
            message.chat.id,
            text=_("A game lobby already exists in this chat."),
        )
        return
    game.starter = message.from_user
    game.owner.add(message.from_user.id)
    await send_message(
        bot,
        message.chat.id,
        text=TEAM_MODE_PICKER_TEXT,
        parse_mode=ParseMode.HTML,
        reply_markup=_team_mode_picker_keyboard(),
    )


@router.message(Command("teamname"))
async def team_name(message: Message, bot: Bot, command: CommandObject) -> None:
    if message.chat.type == "private":
        return
    game = gm.get_active_game(message.chat.id)
    if not game or not game.is_team_mode or game.started:
        await send_message(bot, message.chat.id, text=_("No active team lobby to rename."))
        return
    if not await user_is_creator_or_admin_aiogram(message.from_user, game, bot, message.chat):
        await send_message(
            bot,
            message.chat.id,
            text=_("Only the game creator ({name}) and admin can do that.").format(
                name=display_name_html(game.starter)
            ),
            parse_mode=ParseMode.HTML,
        )
        return
    args = (command.args or "").strip().split(maxsplit=1)
    if len(args) < 2:
        await send_message(bot, message.chat.id, text="Usage: /teamname <A|B> <name>")
        return
    team_id = args[0].upper()
    if not game.set_team_name(team_id, args[1]):
        await send_message(bot, message.chat.id, text=_("Invalid team name or team id."))
        return
    await send_message(
        bot,
        message.chat.id,
        text=_team_lobby_text(game),
        parse_mode=ParseMode.HTML,
        reply_markup=_team_lobby_keyboard(game),
    )


@router.message(Command("kill"))
async def kill_game(message: Message, bot) -> None:
    chat = message.chat
    user = message.from_user
    games = gm.chatid_games.get(chat.id)

    if message.chat.type == "private":
        await send_private_menu(message, bot)
        return

    if not games:
        await send_message(
            bot,
            chat.id,
            text=_("There is no running game in this chat."),
        )
        return

    game = games[-1]

    if await user_is_creator_or_admin_aiogram(user, game, bot, chat):
        try:
            await delete_game_turn_prompt_safe(bot, game)
            ctx = capture_match_context(game, fallback_user=user)
            gm.end_game(chat, user, reason="killed_admin")
            await send_post_match_scoreboard(bot, chat.id, ctx)
            await send_message(
                bot,
                chat.id,
                text=__("ɢᴀᴍᴇ ᴇɴᴅᴇᴅ!", multi=game.translate),
            )
        except NoGameInChatError:
            await send_message(
                bot,
                chat.id,
                text=_(
                    "The game is not started yet. "
                    "Join the game with /join and start the game with /start"
                ),
                reply_to_message_id=message.message_id,
            )
    else:
        await send_message(
            bot,
            chat.id,
            text=_("Only the game creator ({name}) and admin can do that.").format(
                name=display_name_html(game.starter)
            ),
            parse_mode=ParseMode.HTML,
            reply_to_message_id=message.message_id,
        )


@router.message(Command("join"))
async def join_game(message: Message, bot) -> None:
    chat = message.chat
    if message.chat.type == "private":
        await send_private_menu(message, bot)
        return
    if await _dm_start_required_guard(message, bot):
        return

    await _join_active_lobby(
        bot,
        chat,
        message.from_user,
        reply_to_message_id=message.message_id,
    )


@router.message(Command("leave"))
async def leave_game(message: Message, bot) -> None:
    chat = message.chat
    user = message.from_user
    g = gm.get_active_game(chat.id)
    if g and g.is_team_mode and not g.started:
        g.leave_team_lobby(user.id)
        removed_from_game = False
        try:
            gm.leave_game(user, chat)
            removed_from_game = True
        except NoGameInChatError:
            removed_from_game = False
        except NotEnoughPlayersError:
            # In tiny pre-start lobbies, keep lobby alive and only clear team slot.
            removed_from_game = False
        if removed_from_game or g.team_of(user.id) is None:
            await send_message(
                bot,
                chat.id,
                text=_("You left the team lobby."),
                reply_markup=_team_lobby_keyboard(g),
                parse_mode=ParseMode.HTML,
            )
            return
    player = gm.player_for_user_in_chat(user, chat)

    if player is None:
        await send_message(
            bot,
            chat.id,
            text=_("You are not playing in a game in " "this group."),
            reply_to_message_id=message.message_id,
        )
        return

    game = player.game

    try:
        gm.leave_game(user, chat)
    except NoGameInChatError:
        await send_message(
            bot,
            chat.id,
            text=_("You are not playing in a game in " "this group."),
            reply_to_message_id=message.message_id,
        )
    except NotEnoughPlayersError:
        await delete_game_turn_prompt_safe(bot, game)
        ctx = capture_match_context(game, fallback_user=user)
        
        # Special handling for 2-player games: leaver gets penalty, remaining player wins
        if len(game.players) == 2 and game.started:
            remaining_player = None
            for p in game.players:
                if p.user.id != user.id:
                    remaining_player = p.user
                    break
            
            if remaining_player:
                # Preserve historical placements and append the default winner
                # only if they are not already in finish_order.
                existing_finish = list(getattr(game, "finish_order", []) or [])
                if remaining_player.id not in existing_finish:
                    existing_finish.append(remaining_player.id)
                game.finish_order = existing_finish

                # Keep full participant history; ensure both current users are present.
                existing_participants = list(getattr(game, "participant_ids", []) or [])
                if user.id not in existing_participants:
                    existing_participants.append(user.id)
                if remaining_player.id not in existing_participants:
                    existing_participants.append(remaining_player.id)
                game.participant_ids = existing_participants

                # Mirror the same ordering in scoreboard context.
                ctx["finish_order"] = list(game.finish_order)
                ctx["participant_ids"] = list(game.participant_ids)
                # End with special reason to trigger point calculation
                gm.end_game(chat, user, reason="player_left_2p")
                await send_post_match_scoreboard(bot, chat.id, ctx)
                await send_message(
                    bot,
                    chat.id,
                    text=(
                        f"<tg-emoji emoji-id=\"6314237464315696206\">🏆</tg-emoji>"
                        f"<b>ɢᴀᴍᴇ ᴇɴᴅᴇᴅ!</b>\n\n"
                        f"{display_name_html(remaining_player)} ᴡɪɴꜱ ʙʏ ꜱᴄᴀʀɪɴɢ ᴛʜᴇᴍ ᴀᴡᴀʏ 😎\n\n"
                        f"<i>ᴏᴘᴘᴏɴᴇɴᴛ ᴄʜᴏꜱᴇ ᴇꜱᴄᴀᴘᴇ ᴏᴠᴇʀ ᴅᴇꜰᴇᴀᴛ 🏃</i>"
                    ),
                    parse_mode=ParseMode.HTML,
                )
            else:
                gm.end_game(chat, user, reason="not_enough_players")
                await send_post_match_scoreboard(bot, chat.id, ctx)
                await send_message(
                    bot,
                    chat.id,
                    text=(
                        f"<tg-emoji emoji-id=\"6314237464315696206\">🏁</tg-emoji>"
                        f"<b>ɢᴀᴍᴇ ᴇɴᴅᴇᴅ!</b>\n\n"
                        f"<i>ɴᴏᴛ ᴇɴᴏᴜɢʜ ᴘʟᴀʏᴇʀꜱ</i>"
                    ),
                    parse_mode=ParseMode.HTML,
                )
        else:
            gm.end_game(chat, user, reason="not_enough_players")
            await send_post_match_scoreboard(bot, chat.id, ctx)
            await send_message(
                bot,
                chat.id,
                text=(
                    f"<tg-emoji emoji-id=\"6314237464315696206\">🏁</tg-emoji>"
                    f"<b>ɢᴀᴍᴇ ᴇɴᴅᴇᴅ!</b>\n\n"
                    f"<i>ɴᴏᴛ ᴇɴᴏᴜɢʜ ᴘʟᴀʏᴇʀꜱ</i>"
                ),
                parse_mode=ParseMode.HTML,
            )
    else:
        # For 3+ player games, continue the game and apply penalty to leaver
        if game.started and len(game.players) >= 3:
            # Apply abandon penalty to the leaver
            from services.match_service import apply_abandon_penalty_points
            apply_abandon_penalty_points(user.id, -abs(ABANDON_PENALTY))
            
            cancel_fast_countdown(game)
            await send_message(
                bot,
                chat.id,
                text=__(
                    "{name} left the game (-{penalty} points). Game continues!",
                    multi=game.translate,
                ).format(
                    name=display_name_html(user),
                    penalty=abs(ABANDON_PENALTY),
                ),
                parse_mode=ParseMode.HTML,
                reply_to_message_id=message.message_id,
            )
            from no_mercy.ui.prompt import send_turn_prompt_compat

            await send_turn_prompt_compat(
                bot,
                game,
                __("ɴᴇxᴛ ᴘʟᴀʏᴇʀ: {name}", multi=game.translate).format(
                    name=display_name_html(game.current_player.user)
                ),
                reply_to_message_id=message.message_id,
            )
            await start_player_countdown(bot, game)
        elif game.started:
            # 2-player game that didn't trigger NotEnoughPlayersError (edge case)
            cancel_fast_countdown(game)
            from no_mercy.ui.prompt import send_turn_prompt_compat

            await send_turn_prompt_compat(
                bot,
                game,
                __("ɴᴇxᴛ ᴘʟᴀʏᴇʀ: {name}", multi=game.translate).format(
                    name=display_name_html(game.current_player.user)
                ),
                reply_to_message_id=message.message_id,
            )
            await start_player_countdown(bot, game)
        else:
            await send_message(
                bot,
                chat.id,
                text=__("{name} left the game before it started.", multi=game.translate).format(
                    name=display_name_html(user)
                ),
                parse_mode=ParseMode.HTML,
                reply_to_message_id=message.message_id,
            )


@router.message(Command("kick"))
async def kick_player(message: Message, bot) -> None:
    if message.chat.type == "private":
        await send_private_menu(message, bot)
        return

    chat = message.chat
    user = message.from_user
    game = gm.get_active_game(chat.id)
    if not game:
        await send_message(
            bot,
            chat.id,
            text=_(
                "No game is running at the moment. " "Create a new game with /new"
            ),
            reply_to_message_id=message.message_id,
        )
        return

    if not game.started:
        await send_message(
            bot,
            chat.id,
            text=_(
                "The game is not started yet. "
                "Join the game with /join and start the game with /start"
            ),
            reply_to_message_id=message.message_id,
        )
        return

    if not await user_is_creator_or_admin_aiogram(user, game, bot, chat):
        await send_message(
            bot,
            chat.id,
            text=_("Only the game creator ({name}) and admin can do that.").format(
                name=display_name_html(game.starter)
            ),
            parse_mode=ParseMode.HTML,
            reply_to_message_id=message.message_id,
        )
        return

    if not message.reply_to_message:
        await send_message(
            bot,
            chat.id,
            text=_(
                "Please reply to the person you want to kick and type /kick again."
            ),
            reply_to_message_id=message.message_id,
        )
        return

    kicked = message.reply_to_message.from_user
    try:
        gm.leave_game(kicked, chat)
    except NoGameInChatError:
        await send_message(
            bot,
            chat.id,
            text=_("Player {name} is not found in the current game.").format(
                name=display_name_html(kicked)
            ),
            parse_mode=ParseMode.HTML,
            reply_to_message_id=message.message_id,
        )
        return
    except NotEnoughPlayersError:
        await delete_game_turn_prompt_safe(bot, game)
        ctx = capture_match_context(game, fallback_user=user)
        gm.end_game(chat, user, reason="not_enough_players")
        await send_post_match_scoreboard(bot, chat.id, ctx)
        await send_message(
            bot,
            chat.id,
            text=_(
                "{0} was kicked by {1}".format(
                    display_name_html(kicked), display_name_html(user)
                )
            ),
            parse_mode=ParseMode.HTML,
        )
        await send_message(
            bot,
            chat.id,
            text=__("ɢᴀᴍᴇ ᴇɴᴅᴇᴅ!", multi=game.translate),
        )
        return

    await send_message(
        bot,
        chat.id,
        text=_(
            "{0} was kicked by {1}".format(
                display_name_html(kicked), display_name_html(user)
            )
        ),
        parse_mode=ParseMode.HTML,
    )
    cancel_fast_countdown(game)
    from no_mercy.ui.prompt import send_turn_prompt_compat

    await send_turn_prompt_compat(
        bot,
        game,
        __("ɴᴇxᴛ ᴘʟᴀʏᴇʀ: {name}", multi=game.translate).format(
            name=display_name_html(game.current_player.user)
        ),
        reply_to_message_id=message.message_id,
    )
    await start_player_countdown(bot, game)


@router.message(Command("expel"))
async def expel_player(message: Message, bot) -> None:
    """
    Remove a player from the lobby or an in-progress game (AFK / not taking turns).
    Same permission as /kick: group admins or game host (owner).
    Unlike /kick, works before /start so idle lobby members can be removed.
    """
    if message.chat.type == "private":
        await send_private_menu(message, bot)
        return

    chat = message.chat
    user = message.from_user
    game = gm.get_active_game(chat.id)
    if not game:
        await send_message(
            bot,
            chat.id,
            text=_(
                "No game is running at the moment. " "Create a new game with /new"
            ),
            reply_to_message_id=message.message_id,
        )
        return

    if not await user_is_creator_or_admin_aiogram(user, game, bot, chat):
        await send_message(
            bot,
            chat.id,
            text=_("Only the game creator ({name}) and admin can do that.").format(
                name=display_name_html(game.starter)
            ),
            parse_mode=ParseMode.HTML,
            reply_to_message_id=message.message_id,
        )
        return

    if not message.reply_to_message:
        await send_message(
            bot,
            chat.id,
            text=_(
                "Reply to the member you want to remove, then send /expel."
            ),
            reply_to_message_id=message.message_id,
        )
        return

    expelled = message.reply_to_message.from_user
    try:
        gm.leave_game(expelled, chat)
    except NoGameInChatError:
        await send_message(
            bot,
            chat.id,
            text=_("Player {name} is not found in the current game.").format(
                name=display_name_html(expelled)
            ),
            parse_mode=ParseMode.HTML,
            reply_to_message_id=message.message_id,
        )
        return
    except NotEnoughPlayersError:
        cancel_fast_countdown(game)
        await delete_game_turn_prompt_safe(bot, game)
        ctx = capture_match_context(game, fallback_user=user)
        gm.end_game(chat, user, reason="not_enough_players")
        await send_post_match_scoreboard(bot, chat.id, ctx)
        await send_message(
            bot,
            chat.id,
            text=_("{0} was expelled by {1}").format(
                display_name_html(expelled), display_name_html(user)
            ),
            parse_mode=ParseMode.HTML,
        )
        await send_message(
            bot,
            chat.id,
            text=__("ɢᴀᴍᴇ ᴇɴᴅᴇᴅ!", multi=game.translate),
        )
        return

    await send_message(
        bot,
        chat.id,
        text=_("{0} was expelled by {1}").format(
            display_name_html(expelled), display_name_html(user)
        ),
        parse_mode=ParseMode.HTML,
    )
    if game.started:
        cancel_fast_countdown(game)
        from no_mercy.ui.prompt import send_turn_prompt_compat

        await send_turn_prompt_compat(
            bot,
            game,
            __("ɴᴇxᴛ ᴘʟᴀʏᴇʀ: {name}", multi=game.translate).format(
                name=display_name_html(game.current_player.user)
            ),
            reply_to_message_id=message.message_id,
        )
        await start_player_countdown(bot, game)


@router.message(Command("start"))
async def start_game(message: Message, bot: Bot, command: CommandObject) -> None:
    if message.chat.type != "private":
        n = push_game_locales_for_user_chat(message.from_user, message.chat)
        try:
            chat = message.chat
            game = gm.get_active_game(chat.id)
            if not game:
                await send_message(
                    bot,
                    chat.id,
                    text=_(
                        "There is no game running in this chat. Create "
                        "a new one with /new"
                    ),
                )
                return
            if game.started:
                await send_message(
                    bot, chat.id, text=_("The game has already started")
                )
            elif not await user_is_creator_or_admin_aiogram(message.from_user, game, bot, chat):
                await send_message(
                    bot,
                    chat.id,
                    text=_("Only the game creator ({name}) and admin can do that.").format(
                        name=display_name_html(game.starter)
                    ),
                    parse_mode=ParseMode.HTML,
                )
            elif len(game.players) < MIN_PLAYERS:
                await send_message(
                    bot,
                    chat.id,
                    text=__(
                        "At least {minplayers} players must /join the game "
                        "before you can start it"
                    ).format(minplayers=MIN_PLAYERS),
                )
            else:
                if game.is_team_mode:
                    if not game.team_ready():
                        await send_message(
                            bot,
                            chat.id,
                            text=_("Both teams must be full before starting."),
                        )
                        return
                    by_uid = {int(p.user.id): p for p in game.players}
                    if set(by_uid.keys()) != set(game.team_members["A"] + game.team_members["B"]):
                        await send_message(
                            bot,
                            chat.id,
                            text=_("All selected team members must /join before /start."),
                        )
                        return
                    game.start(deal_hands=False)
                    try:
                        ok = game.initialize_team_runtime(game.players)
                    except Exception:
                        ok = False
                    if not ok:
                        await send_message(
                            bot,
                            chat.id,
                            text=_("Could not initialize team turn order. Recreate the lobby."),
                        )
                        return
                    first_message = (
                        "<b>TEAM UNO %dv%d STARTED</b>\n"
                        "A: <b>%s</b> (%d cards)\n"
                        "B: <b>%s</b> (%d cards)\n"
                        "First player: %s\n"
                        "Top card: %s"
                        % (
                            game.team_size,
                            game.team_size,
                            _team_title(game, "A"),
                            game.team_cards_left("A"),
                            _team_title(game, "B"),
                            game.team_cards_left("B"),
                            display_name_html(game.current_player.user),
                            repr(game.last_card),
                        )
                    )
                else:
                    game.start()
                    first_message = (
                        __(
                            "First player: {name}\n"
                            "Use /close to stop people from joining the game.",
                            multi=game.translate,
                        ).format(name=display_name_html(game.current_player.user))
                    )
                schedule_audit_telegram(
                    "game_started",
                    action="match_start",
                    chat=format_chat(chat),
                    game_mode=getattr(game, "mode", ""),
                    team_mode=bool(getattr(game, "is_team_mode", False)),
                    started_by=format_user(message.from_user),
                    players=players_snapshot(game),
                )
                choice = [[btn_switch_current_chat(_("Make your choice!"), "", "success")]]
                await send_sticker(bot, chat.id, sticker=c.sticker_for(game.last_card, game))
                from no_mercy.ui.prompt import send_turn_prompt_compat

                await send_turn_prompt_compat(
                    bot,
                    game,
                    first_message,
                    markup(choice),
                )
                await start_player_countdown(bot, game)
        finally:
            pop_locale_stack_n(n)
        return

    user_service.ensure_user_dm_initialized(message.from_user)
    schedule_audit_telegram(
        "user_started_bot_dm",
        action="private_start",
        user=format_user(message.from_user),
    )
    arg_line = (command.args or "").strip()
    first = arg_line.split()[0].lower() if arg_line else ""
    if first == "select":
        uid = message.from_user.id
        gm.prune_stale_player_refs_for_user(uid)
        players = gm.userid_players.get(uid) or []
        if not players:
            await send_message(
                bot,
                message.chat.id,
                text=_(
                    "You are not in any active game. Join a group game with "
                    "/join first, then use inline play from that group."
                ),
            )
        else:
            current = gm.userid_current.get(uid)
            groups = []
            for player in players:
                title = player.game.chat.title or ""
                if current is not None and player == current:
                    title = "- %s -" % title
                groups.append(
                    [btn_callback(title, str(player.game.chat.id), "default")]
                )
            await send_message(
                bot,
                message.chat.id,
                text=_("Please select the group you want to play in."),
                reply_markup=markup(groups),
            )
        return

    await send_private_menu(message, bot)


@router.message(Command("close"))
async def close_game(message: Message, bot) -> None:
    chat = message.chat
    user = message.from_user
    games = gm.chatid_games.get(chat.id)
    if not games:
        await send_message(
            bot,
            chat.id,
            text=_("There is no running game in this chat."),
        )
        return
    game = games[-1]
    if user.id in game.owner:
        game.open = False
        await send_message(
            bot,
            chat.id,
            text=_(
                "Closed the lobby. " "No more players can join this game."
            ),
        )
    else:
        await send_message(
            bot,
            chat.id,
            text=_("Only the game creator ({name}) and admin can do that.").format(
                name=display_name_html(game.starter)
            ),
            parse_mode=ParseMode.HTML,
            reply_to_message_id=message.message_id,
        )


@router.message(Command("open"))
async def open_game(message: Message, bot) -> None:
    chat = message.chat
    user = message.from_user
    games = gm.chatid_games.get(chat.id)
    if not games:
        await send_message(
            bot,
            chat.id,
            text=_("There is no running game in this chat."),
        )
        return
    game = games[-1]
    if user.id in game.owner:
        game.open = True
        await send_message(
            bot,
            chat.id,
            text=_("Opened the lobby. " "New players may /join the game."),
        )
    else:
        await send_message(
            bot,
            chat.id,
            text=_("Only the game creator ({name}) and admin can do that.").format(
                name=display_name_html(game.starter)
            ),
            parse_mode=ParseMode.HTML,
            reply_to_message_id=message.message_id,
        )


@router.message(Command("cancel_lobby"))
async def cancel_lobby_command(message: Message, bot: Bot) -> None:
    if message.chat.type == "private":
        await send_private_menu(message, bot)
        return
    chat = message.chat
    user = message.from_user
    game = gm.get_active_game(chat.id)
    err = await _try_cancel_lobby(bot, chat, user, game)
    if err is None:
        await send_message(
            bot,
            chat.id,
            text=_cancel_lobby_success_html(),
            parse_mode=ParseMode.HTML,
            reply_to_message_id=message.message_id,
        )
        return
    if err == "no_game":
        await send_message(
            bot,
            chat.id,
            text=_(
                "❌ ɴᴏ ʟᴏʙʙʏ ɪꜱ ᴏᴘᴇɴ ʀɪɢʜᴛ ɴᴏᴡ.\n🎮 ᴄʀᴇᴀᴛᴇ ᴏɴᴇ ᴜꜱɪɴɢ /new"
            ),
            reply_to_message_id=message.message_id,
        )
        return
    if err == "started":
        await send_message(
            bot,
            chat.id,
            text=_(
                "⚔️ ᴛʜᴇ ɢᴀᴍᴇ ʜᴀꜱ ᴀʟʀᴇᴀᴅʏ ꜱᴛᴀʀᴛᴇᴅ.\n"
                "💀 ᴜꜱᴇ /kill ᴛᴏ ꜱᴛᴏᴘ ɪᴛ (ʜᴏꜱᴛ ᴏʀ ᴀᴅᴍɪɴ ᴏɴʟʏ)."
            ),
            reply_to_message_id=message.message_id,
        )
        return
    if err == "denied":
        st = game.starter if game else None
        await send_message(
            bot,
            chat.id,
            text=_(
                "🚫 ᴏɴʟʏ ᴛʜᴇ ʟᴏʙʙʏ ᴄʀᴇᴀᴛᴏʀ ({name}) "
                "ᴏʀ ɢʀᴏᴜᴘ ᴀᴅᴍɪɴꜱ ᴄᴀɴ ᴄᴀɴᴄᴇʟ ᴛʜɪꜱ ʟᴏʙʙʏ."
            ).format(
                name=display_name_html(st) if st else "—"
            ),
            parse_mode=ParseMode.HTML,
            reply_to_message_id=message.message_id,
        )
        return
    await send_message(
        bot,
        chat.id,
        text=_("❌ ꜰᴀɪʟᴇᴅ ᴛᴏ ᴄᴀɴᴄᴇʟ ᴛʜᴇ ʟᴏʙʙʏ 😭\nᴘʟᴇᴀꜱᴇ ᴛʀʏ ᴀɢᴀɪɴ."),
        reply_to_message_id=message.message_id,
    )


@router.message(Command("handsize"))
async def set_hand_size_command(message: Message, bot, command: CommandObject):
    chat = message.chat
    if chat.type == "private":
        return
    try:
        game = gm.get_active_game(chat.id)
    except NoGameInChatError:
        await send_message(bot, chat.id, text="No active game in this chat.")
        return
    if not game:
        await send_message(bot, chat.id, text="No active game in this chat.")
        return
    if game.started:
        await send_message(bot, chat.id, text="Cannot change hand size after game has started.")
        return
    # Permission check
    is_owner = game.starter and message.from_user.id == game.starter.id
    is_admin = await user_is_creator_or_admin_aiogram(message.from_user, game, bot, chat)
    if not is_owner and not is_admin:
        await send_message(bot, chat.id, text="Only the game creator or an admin can change hand size.")
        return
    # Parse argument
    raw = (command.args or "").strip()
    if not raw.isdigit():
        current = game.effective_hand_size()
        await send_message(
            bot, chat.id,
            text= "<tg-emoji emoji-id=\"5904258298764334001\">✨</tg-emoji><b>ʜᴀɴᴅ sɪᴢᴇ sᴇᴛᴛɪɴɢs</b>\nᴄᴜʀʀᴇɴᴛ: <b>%d ᴄᴀʀᴅs</b> ᴘᴇʀ ᴘʟᴀʏᴇʀ\nᴜsᴀɢᴇ: <code>/handsize &lt;number&gt;</code>\nᴇxᴀᴍᴘʟᴇ: <code>/handsize 14</code>\n\nᴍᴜsᴛ ʙᴇ ᴀ ᴍᴜʟᴛɪᴘʟᴇ ᴏғ 7 (ᴍɪɴɪᴍᴜᴍ 7)." % current,
            parse_mode=ParseMode.HTML
        )
        return
    size = int(raw)
    if size < 7 or size % 7 != 0:
        await send_message(
            bot, chat.id,
            text="⚠️ Hand size must be a multiple of 7 (minimum 7).\n\nExamples: 7, 14, 21, 28, 35...",
            parse_mode=ParseMode.HTML
        )
        return
    game.hand_size = size
    await send_message(
        bot, chat.id,
        text="✅ Hand card size has been changed to %d" % size,
        parse_mode=ParseMode.HTML
    )


@router.message(Command("skip"))
async def skip_player(message: Message, bot) -> None:
    n = push_game_locales_for_user_chat(message.from_user, message.chat)
    try:
        chat = message.chat
        user = message.from_user
        player = gm.player_for_user_in_chat(user, chat)
        if not player:
            await send_message(
                bot,
                chat.id,
                text=_("You are not playing in a game in this chat."),
            )
            return
        game = player.game
        skipped_player = game.current_player
        started = skipped_player.turn_started
        now = datetime.now()
        delta = (now - started).seconds
        if delta < skipped_player.waiting_time and player != skipped_player:
            wait_left = skipped_player.waiting_time - delta
            await send_message(
                bot,
                chat.id,
                text=_(
                    "Please wait {time} second",
                    "Please wait {time} seconds",
                    wait_left,
                ).format(time=wait_left),
                reply_to_message_id=message.message_id,
            )
        else:
            await do_skip(bot, player, from_scheduled_job=False)
    finally:
        pop_locale_stack_n(n)


@router.callback_query(F.data.startswith(NEW_MODE_PREFIX))
async def new_mode_callback(query, bot: Bot) -> None:
    data = query.data or ""
    parts = data.split("|")
    if len(parts) < 4 or parts[1] != "pick":
        await answer_callback_query_safe(query)
        return
    mode = parts[2]
    token = parts[3]
    if mode not in {
        "classic",
        "fast",
        "wild",
        "rainbow",
        "text",
        "team",
        "sudden_death",
        "no_mercy",
    }:
        await answer_callback_query_safe(query, text="Invalid mode", show_alert=True)
        return
    chat = query.message.chat if query.message else None
    if chat is None:
        await answer_callback_query_safe(query)
        return
    chat_id = chat.id
    st = _pending_new_mode.get(chat_id)
    if not st:
        await answer_callback_query_safe(query, text="Selector expired", show_alert=True)
        return
    if st.get("token") != token:
        await answer_callback_query_safe(query, text="Stale selector", show_alert=True)
        return
    if (time.time() - float(st.get("created_at") or 0.0)) > NEW_MODE_TTL_SEC:
        _pending_new_mode.pop(chat_id, None)
        await answer_callback_query_safe(query, text="Selector expired", show_alert=True)
        return
    actor = query.from_user
    if actor.id != int(st.get("owner_id") or 0):
        if not await user_is_admin_aiogram(actor, bot, chat):
            await answer_callback_query_safe(query, text="Only creator/admin can choose", show_alert=True)
            return
    if st.get("processed"):
        await answer_callback_query_safe(query, text="Mode already selected", show_alert=True)
        return
    if gm.get_active_game(chat_id) is not None:
        _pending_new_mode.pop(chat_id, None)
        await answer_callback_query_safe(query, text="Game already exists", show_alert=True)
        return
    st["processed"] = True
    game = await _create_lobby_for_mode(bot, chat, actor, mode)
    _pending_new_mode.pop(chat_id, None)
    if game is None:
        await answer_callback_query_safe(query, text="Could not create lobby", show_alert=True)
        return
    try:
        await safe_edit_message_text(
            query,
            "<b>ʟᴏʙʙʏ ᴄʀᴇᴀᴛᴇᴅ</b>\n" + _("Mode selected successfully."),
            parse_mode=ParseMode.HTML,
            reply_markup=None,
        )
    except Exception:
        pass
    await answer_callback_query_safe(query, text="Mode selected")


@router.callback_query(F.data.startswith(LOBBY_PREFIX))
async def lobby_controls_callback(query, bot: Bot) -> None:
    data = query.data or ""
    parts = data.split("|")
    if len(parts) < 2:
        await answer_callback_query_safe(query)
        return
    action = parts[1]
    chat = query.message.chat if query.message else None
    if chat is None:
        await answer_callback_query_safe(query)
        return
    game = gm.get_active_game(chat.id)
    if not game:
        await answer_callback_query_safe(query, text="No active game in this chat.", show_alert=True)
        return
    # Only validate gid for actions that need it (join, start, close)
    # Settings actions (settings, hs, stack, deck, back) don't need gid validation
    if action in ("join", "start", "close", "cancel"):
        if len(parts) < 3:
            await answer_callback_query_safe(query)
            return
        gid = parts[2]
        if str(getattr(game, "match_uuid", "")) != gid:
            await answer_callback_query_safe(query, text="Lobby is stale", show_alert=True)
            return
    user = query.from_user
    if action == "join":
        fake_msg = type("M", (), {"chat": chat, "from_user": user, "message_id": query.message.message_id})()
        if await _dm_start_required_guard(fake_msg, bot):
            await answer_callback_query_safe(query)
            return
        await _join_active_lobby(bot, chat, user, reply_to_message_id=query.message.message_id)
        await answer_callback_query_safe(query, text="Join processed")
        return
    if action == "close":
        if not await user_is_creator_or_admin_aiogram(user, game, bot, chat):
            await answer_callback_query_safe(query, text="Only host/admin can close", show_alert=True)
            return
        game.open = False
        await answer_callback_query_safe(query, text="Lobby closed")
        await send_message(bot, chat.id, text=_("Closed the lobby. No more players can join this game."))
        return
    if action == "cancel":
        err = await _try_cancel_lobby(bot, chat, user, game)
        if err == "denied":
            await answer_callback_query_safe(
                query, text="Only host/admin can cancel", show_alert=True
            )
            return
        if err == "started":
            await answer_callback_query_safe(
                query, text="Match in progress — use /kill", show_alert=True
            )
            return
        if err in ("no_game", "failed"):
            await answer_callback_query_safe(
                query, text="Could not cancel lobby", show_alert=True
            )
            return
        try:
            await safe_edit_message_text(
                query,
                _cancel_lobby_success_html(),
                parse_mode=ParseMode.HTML,
                reply_markup=None,
            )
        except Exception:
            await send_message(
                bot,
                chat.id,
                text=_cancel_lobby_success_html(),
                parse_mode=ParseMode.HTML,
            )
        await answer_callback_query_safe(query, text="Lobby cancelled")
        return
    if action == "start":
        if not await user_is_creator_or_admin_aiogram(user, game, bot, chat):
            await answer_callback_query_safe(query, text="Only host/admin can start", show_alert=True)
            return
        if game.started:
            await answer_callback_query_safe(query, text="Game already started", show_alert=True)
            return
        if len(game.players) < MIN_PLAYERS:
            await answer_callback_query_safe(query, text="Not enough players", show_alert=True)
            return
        game.start()
        first_message = __(
            "First player: {name}\nUse /close to stop people from joining the game.",
            multi=game.translate,
        ).format(name=display_name_html(game.current_player.user))
        choice = [[btn_switch_current_chat(_("Make your choice!"), "", "success")]]
        await send_sticker(bot, chat.id, sticker=c.sticker_for(game.last_card, game))
        from no_mercy.ui.prompt import send_turn_prompt_compat

        await send_turn_prompt_compat(
            bot,
            game,
            first_message,
            markup(choice),
        )
        await start_player_countdown(bot, game)
        await answer_callback_query_safe(query, text="Game started")
        return

    # Settings -> Hand Size sub-panel
    elif action == "settings" and len(parts) == 3 \
            and parts[2] == "handsize":
        await answer_callback_query_safe(query)
        await safe_edit_message_text(
            query,
            _handsize_text(game),
            _handsize_keyboard(game),
        )

    # Settings -> Draw Stack sub-panel
    elif action == "settings" and len(parts) == 3 \
            and parts[2] == "drawstack":
        await answer_callback_query_safe(query)
        await safe_edit_message_text(
            query,
            _drawstack_text(game),
            _drawstack_keyboard(game),
        )

    # Settings -> Deck Style sub-panel
    elif action == "settings" and len(parts) == 3 \
            and parts[2] == "deckstyle":
        await answer_callback_query_safe(query)
        await safe_edit_message_text(
            query,
            _deckstyle_text(game),
            _deckstyle_keyboard(game),
        )

    # Settings main panel (supports legacy lb|settings|{gid} callbacks)
    elif action == "settings":
        await answer_callback_query_safe(query)
        await safe_edit_message_text(
            query,
            _settings_main_text(game),
            _settings_main_keyboard(game),
        )

    # Hand size selection: lb|hs|7 / lb|hs|14 / lb|hs|21
    elif action == "hs":
        if game.mode == "no_mercy":
            await answer_callback_query_safe(
                query,
                text="🔥 %s" % smallcaps("NO MERCY uses a fixed 7-card hand."),
                show_alert=True,
            )
            return
        if game.started:
            await answer_callback_query_safe(
                query,
                text="Cannot change hand size after "
                     "game has started.",
                show_alert=True
            )
            return
        if not await _is_lobby_owner_or_admin(query, game, bot):
            await answer_callback_query_safe(
                query,
                text="Only the game creator can "
                     "change settings.",
                show_alert=True
            )
            return
        try:
            size = int(parts[2])
        except (IndexError, ValueError):
            await answer_callback_query_safe(
                query,
                text="Invalid hand size.",
                show_alert=True
            )
            return
        if size < 7 or size % 7 != 0 or size > 21:
            await answer_callback_query_safe(
                query,
                text="Hand size must be 7, 14, or 21.",
                show_alert=True
            )
            return
        game.hand_size = size
        await answer_callback_query_safe(
            query,
            text="Hand size set to %d cards." % size,
            show_alert=False
        )
        await safe_edit_message_text(
            query,
            _handsize_text(game),
            _handsize_keyboard(game),
        )

    # Draw stack toggle: lb|stack|on / lb|stack|off
    elif action == "stack":
        if game.mode == "no_mercy":
            await answer_callback_query_safe(
                query,
                text="🔥 %s" % smallcaps("NO MERCY always has draw stacking ON."),
                show_alert=True,
            )
            return
        if game.started:
            await answer_callback_query_safe(
                query,
                text="Cannot change settings after "
                     "game has started.",
                show_alert=True
            )
            return
        if not await _is_lobby_owner_or_admin(query, game, bot):
            await answer_callback_query_safe(
                query,
                text="Only the game creator can "
                     "change settings.",
                show_alert=True
            )
            return
        game.stacking_enabled = (
            len(parts) > 2 and parts[2] == "on"
        )
        state = "ON" if game.stacking_enabled else "OFF"
        await answer_callback_query_safe(
            query,
            text="Draw Stacking %s." % state,
            show_alert=False
        )
        await safe_edit_message_text(
            query,
            _drawstack_text(game),
            _drawstack_keyboard(game),
        )

    # Deck style: lb|deck|normal / anime / pokemon (classic -> normal alias)
    elif action == "deck":
        if game.mode == "no_mercy":
            await answer_callback_query_safe(
                query,
                text="🔥 %s" % smallcaps("NO MERCY uses its own premium card art."),
                show_alert=True,
            )
            return
        if game.started:
            await answer_callback_query_safe(
                query,
                text="Cannot change settings after game has started.",
                show_alert=True,
            )
            return
        if not await _is_lobby_owner_or_admin(query, game, bot):
            await answer_callback_query_safe(
                query,
                text="Only the game creator can change settings.",
                show_alert=True,
            )
            return
        if len(parts) < 3:
            await answer_callback_query_safe(query, text="Invalid deck style.", show_alert=True)
            return
        raw = parts[2].strip().lower()
        allowed_raw = {"normal", "classic", "default", "anime", "pokemon", "poke"}
        if raw not in allowed_raw:
            await answer_callback_query_safe(query, text="Invalid deck style.", show_alert=True)
            return
        choice = normalize_deck_style(raw)
        if choice in ALT_DECK_STYLES and not deck_style_selectable_for_mode(game.mode):
            await answer_callback_query_safe(
                query,
                text="Anime and Pokemon decks are not available in Rainbow mode yet.",
                show_alert=True,
            )
            return
        game.deck_style = choice
        label = game.deck_style_display()
        await answer_callback_query_safe(
            query,
            text="Deck style set to %s." % label,
            show_alert=False,
        )
        await safe_edit_message_text(
            query,
            _deckstyle_text(game),
            _deckstyle_keyboard(game),
        )

    # Back: return to lobby from settings main
    elif action == "back":
        await answer_callback_query_safe(query)
        await safe_edit_message_text(
            query,
            _lobby_text(game),
            _lobby_controls_keyboard(game),
        )

    else:
        await answer_callback_query_safe(query)


@router.callback_query(F.data.startswith(TEAM_CB_PREFIX))
async def team_lobby_callback(query, bot: Bot) -> None:
    data = query.data or ""
    payload = data[len(TEAM_CB_PREFIX) :]
    parts = payload.split("|")
    chat_id = query.message.chat.id if query.message else None
    if chat_id is None:
        await answer_callback_query_safe(query)
        return
    game = gm.get_active_game(chat_id)
    if not game:
        await answer_callback_query_safe(query, text="Lobby not found", show_alert=True)
        return
    if game.started:
        await answer_callback_query_safe(query, text="Match already started", show_alert=True)
        return

    chat = query.message.chat if query.message else None
    if chat is None:
        await answer_callback_query_safe(query)
        return

    actor = query.from_user
    action = parts[0] if parts else ""

    if action == "cancel_lobby":
        if len(parts) >= 2:
            if str(getattr(game, "match_uuid", "")) != parts[1]:
                await answer_callback_query_safe(query, text="Lobby is stale", show_alert=True)
                return
        err = await _try_cancel_lobby(bot, chat, actor, game)
        if err == "denied":
            await answer_callback_query_safe(
                query, text="Only host/admin can cancel", show_alert=True
            )
            return
        if err == "started":
            await answer_callback_query_safe(
                query, text="Match already started", show_alert=True
            )
            return
        if err in ("no_game", "failed"):
            await answer_callback_query_safe(
                query, text="Could not cancel lobby", show_alert=True
            )
            return
        try:
            await safe_edit_message_text(
                query,
                _cancel_lobby_success_html(),
                parse_mode=ParseMode.HTML,
                reply_markup=None,
            )
        except Exception:
            await send_message(
                bot,
                chat.id,
                text=_cancel_lobby_success_html(),
                parse_mode=ParseMode.HTML,
            )
        await answer_callback_query_safe(query, text="Lobby cancelled")
        return

    if action == "mode":
        if actor.id not in game.owner:
            await answer_callback_query_safe(query, text="Only host can set mode", show_alert=True)
            return
        if len(parts) < 3:
            await answer_callback_query_safe(query)
            return
        team_size = 2 if parts[1] == "2" else 3
        assignment = "random" if parts[2] == "random" else "manual"
        game.enable_team_mode(team_size, assignment)
        await safe_edit_message_text(
            query,
            _team_lobby_text(game),
            parse_mode=ParseMode.HTML,
            reply_markup=_team_lobby_keyboard(game),
        )
        await answer_callback_query_safe(query, text="Team mode selected")
        return

    if not game.is_team_mode:
        await answer_callback_query_safe(query, text="Select a team mode first", show_alert=True)
        return

    if action == "join":
        if len(parts) < 2:
            await answer_callback_query_safe(query)
            return
        tid = parts[1]
        if game.team_assignment == "random":
            for x in ("A", "B"):
                if actor.id in game.team_members[x]:
                    break
            else:
                if len(game.team_members["A"]) <= len(game.team_members["B"]) and len(game.team_members["A"]) < game.team_size:
                    game.team_members["A"].append(actor.id)
                elif len(game.team_members["B"]) < game.team_size:
                    game.team_members["B"].append(actor.id)
                else:
                    await answer_callback_query_safe(query, text="Lobby full", show_alert=True)
                    return
        else:
            if not game.move_user_to_team(actor.id, tid):
                await answer_callback_query_safe(query, text="Team full", show_alert=True)
                return
        await safe_edit_message_text(
            query,
            _team_lobby_text(game),
            parse_mode=ParseMode.HTML,
            reply_markup=_team_lobby_keyboard(game),
        )
        await answer_callback_query_safe(query, text="Joined")
        return

    if action == "leave":
        game.leave_team_lobby(actor.id)
        try:
            gm.leave_game(actor, query.message.chat)
        except (NoGameInChatError, NotEnoughPlayersError):
            pass
        await safe_edit_message_text(
            query,
            _team_lobby_text(game),
            parse_mode=ParseMode.HTML,
            reply_markup=_team_lobby_keyboard(game),
        )
        await answer_callback_query_safe(query, text="Left lobby")
        return

    if action == "start":
        if actor.id not in game.owner:
            await answer_callback_query_safe(query, text="Only host can start", show_alert=True)
            return
        if not game.team_ready():
            await answer_callback_query_safe(query, text="Fill both teams first", show_alert=True)
            return
        await answer_callback_query_safe(query, text="Use /start to begin")
        await safe_edit_message_text(
            query,
            _team_lobby_text(game),
            parse_mode=ParseMode.HTML,
            reply_markup=_team_lobby_keyboard(game),
        )
        return

    if action == "change_mode":
        if actor.id not in game.owner:
            await answer_callback_query_safe(query, text="Only host can change mode", show_alert=True)
            return
        game.disable_team_mode()
        await safe_edit_message_text(
            query,
            TEAM_MODE_PICKER_TEXT,
            parse_mode=ParseMode.HTML,
            reply_markup=_team_mode_picker_keyboard(),
        )
        await answer_callback_query_safe(query, text="Team mode exited")
        return

    await answer_callback_query_safe(query)


@router.callback_query(F.data.startswith(TEAM_REMATCH_PREFIX))
async def team_rematch_callback(query, bot: Bot) -> None:
    data = query.data or ""
    parts = data.split("|")
    if len(parts) < 3:
        await answer_callback_query_safe(query)
        return
    action = parts[1]
    if action not in ("same", "shuffle"):
        await answer_callback_query_safe(query, text="Unknown rematch action", show_alert=True)
        return
    chat_id = query.message.chat.id if query.message else None
    if chat_id is None:
        await answer_callback_query_safe(query)
        return
    payload = gm.team_rematches.get(chat_id)
    if not payload or payload.get("match_id") != parts[2]:
        await answer_callback_query_safe(query, text="Rematch expired", show_alert=True)
        return
    created_ts = float(payload.get("created_at_ts") or 0.0)
    if created_ts <= 0 or (time.time() - created_ts) > TEAM_REMATCH_TTL_SEC:
        gm.team_rematches.pop(chat_id, None)
        await answer_callback_query_safe(query, text="Rematch expired", show_alert=True)
        return
    allowed = set(int(x) for x in payload.get("players", []))
    if query.from_user.id not in allowed:
        await answer_callback_query_safe(query, text="Only previous players can use this", show_alert=True)
        return
    if gm.get_active_game(chat_id):
        await answer_callback_query_safe(query, text="Finish current lobby/game first", show_alert=True)
        return
    game = gm.new_game(query.message.chat)
    if not game:
        await answer_callback_query_safe(query, text="Cannot create rematch now", show_alert=True)
        return
    game.starter = query.from_user
    game.owner.add(query.from_user.id)
    game.enable_team_mode(int(payload.get("team_size") or 2), "manual")
    game.set_mode(payload.get("mode") or DEFAULT_GAMEMODE)
    game.deck_style = normalize_deck_style(payload.get("deck_style"))
    if payload.get("hand_size") is not None:
        game.hand_size = payload.get("hand_size")
    if "stacking_enabled" in payload:
        game.stacking_enabled = bool(payload.get("stacking_enabled"))
    game.team_names = dict(payload.get("team_names") or {"A": "", "B": ""})
    if action == "same":
        game.team_members["A"] = list(payload.get("teams", {}).get("A", []))
        game.team_members["B"] = list(payload.get("teams", {}).get("B", []))
    else:
        ids = list(allowed)
        game.randomize_teams(ids)
    await send_message(
        bot,
        chat_id,
        text=_team_lobby_text(game) + "\n\nPrevious players must /join, then host runs /start.",
        parse_mode=ParseMode.HTML,
        reply_markup=_team_lobby_keyboard(game),
    )
    gm.team_rematches.pop(chat_id, None)
    await answer_callback_query_safe(query, text="Rematch lobby created")