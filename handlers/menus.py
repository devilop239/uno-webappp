# -*- coding: utf-8 -*-
"""Private menus: /help, main keyboard, /modes, /source, /news, player /stats."""

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from ui.inline_buttons import btn_callback, btn_url, markup
from internationalization import _
from promotions import send_promotion
from services import stats_service
from tg.helpers import (
    answer_callback_query_safe,
    get_bot_username,
    safe_edit_message_text,
    send_message,
)
from ui.text_style import custom_emoji_heading_html, menu_heading_bold, menu_title_bar, smallcaps

router = Router(name="menus")

_BOT_OWNER_NAME = "demon"
_BOT_OWNER_AT = "@demon12809"
_BOT_OWNER_URL = "https://t.me/demon12809"
_SOURCE_CODE_URL = _BOT_OWNER_URL
_SUPPORT_UPDATES_URL = "https://t.me/demon_botzz"

# Premium custom emoji IDs for the private /help welcome (HTML <tg-emoji>).
_WELCOME_EMOJI_UNO = "5415825426633202840"
_WELCOME_EMOJI_GROUP = "6073456529640525999"
_WELCOME_EMOJI_INLINE = "6181690847961027504"
_WELCOME_EMOJI_MENU = "6073220916324602224"


def _footer_menu():
    return markup([[btn_callback(smallcaps(_("« Main menu")), "m|0", "default", icon_role="p12")]])


def _welcome_html(bot_username):
    u = (bot_username or "").lstrip("@")
    inline_line = smallcaps(
        _(
            "Type @{name} followed by a space to open your hand and play cards "
            "directly in the group."
        ).format(name=u)
    )
    return (
        "%s\n\n"
        "%s\n"
        "<code>/new</code> • %s\n"
        "<code>/join</code> • %s\n"
        "<code>/start</code> • %s\n\n"
        "%s\n"
        "%s\n\n"
        "%s\n"
        "<b>ᴄʜᴇᴄᴋ ᴏᴜᴛ ʀᴜʟᴇꜱ ᴏꜰ ᴀʟʟ ᴍᴏᴅᴇꜱ ʙʏ ᴜꜱɪɴɢ /rules_map</b>\n\n"
        "%s"
    ) % (
        custom_emoji_heading_html(_WELCOME_EMOJI_UNO, "🎴", _("UNO")),
        custom_emoji_heading_html(_WELCOME_EMOJI_GROUP, "✨", _("Group gameplay")),
        smallcaps(_("Create a new game lobby")),
        smallcaps(_("Join the current lobby")),
        smallcaps(_("Start the match when enough players have joined")),
        custom_emoji_heading_html(
            _WELCOME_EMOJI_INLINE, "🃏", _("Inline play in groups")
        ),
        inline_line,
        custom_emoji_heading_html(_WELCOME_EMOJI_MENU, "📋", _("Menu")),
        smallcaps(_("Statistics • Help • Support")),
    )


def _main_menu_keyboard():
    return markup(
        [
            [
                btn_callback(smallcaps(_("How to play")), "m|h", "primary", icon_role="p1"),
                btn_callback(smallcaps(_("Modes")), "m|modes", "primary", icon_role="p2"),
            ],
            [btn_callback(smallcaps(_("Statistics")), "ss|home", "danger", icon_role="p4")],
            [
                btn_url(
                    smallcaps(_("Support & updates")),
                    _SUPPORT_UPDATES_URL,
                    "primary",
                    icon_role="p5",
                ),
            ],
            [
                btn_url(
                    smallcaps(_("Owner")),
                    _BOT_OWNER_URL,
                    "success",
                    icon_role="owner_btn",
                ),
            ],
        ]
    )


def _help_submenu_keyboard():
    return markup(
        [
            [btn_callback(smallcaps(_("Quick start")), "m|h1", "primary", icon_role="p7")],
            [
                btn_callback(
                    smallcaps(_("Using inline (your cards)")),
                    "m|h2",
                    "primary",
                    icon_role="p8",
                )
            ],
            [btn_callback(smallcaps(_("Commands in group")), "m|h3", "danger", icon_role="p9")],
            [
                btn_callback(
                    smallcaps(_("Host / admin commands")),
                    "m|h4",
                    "danger",
                    icon_role="p10",
                )
            ],
            [btn_callback(smallcaps(_("« Back")), "m|0", "default", icon_role="p11")],
        ]
    )


def _text_help_quick(bot_username):
    return (
        "%s\n\n"
        "✦ %s\n"
        "✦ %s\n"
        "✦ %s\n"
        "✦ %s\n\n"
        "🃏 %s"
    ) % (
        menu_title_bar("✨", _("Quick start")),
        _("Add the bot to your group."),
        _("Run <code>/new</code> to open a lobby."),
        _("Players use <code>/join</code>."),
        _("When everyone is ready, <code>/start</code> begins the round."),
        _("Then type <code>@%s</code> + space in that group to play inline.")
        % bot_username,
    )


def _text_help_inline(bot_username):
    return (
        "%s\n\n"
        "%s\n\n"
        "%s"
    ) % (
        menu_title_bar("🃏", _("Inline play")),
        _(
            "In the group, type <code>@%s</code> and press <b>space</b> "
            "(or choose <code>via @%s</code> on a message)."
        )
        % (bot_username, bot_username),
        _(
            "Your hand, draw and pass (when allowed), and game info appear here. "
            "Dimmed cards cannot be played at the moment."
        ),
    )


def _text_help_commands():
    return (
        "%s\n\n"
        "<code>/leave</code> · %s\n"
        "<code>/skip</code> · %s\n"
        "<code>/notify_me</code> · %s\n"
        "<code>/help</code> · %s"
    ) % (
        menu_title_bar("📋", _("Group commands")),
        _("Leave the current game"),
        _("Skip a slow player (when the rules allow it)"),
        _("Get a private message when a new game starts in this chat"),
        _("Short tip in groups — full guide in private"),
    )


def _text_help_host():
    return (
        "%s\n\n"
        "<code>/close</code> / <code>/open</code> · %s\n"
        "<code>/kill</code> · %s\n"
        "<code>/kick</code> · %s\n"
        "<code>/expel</code> · %s"
    ) % (
        menu_title_bar("🔷", _("Host and admin")),
        _("Close or reopen the lobby"),
        _("End the current game"),
        _("Reply to a user, then send <code>/kick</code> (during a game)"),
        _("Reply to a user, then send <code>/expel</code> (lobby or game; remove AFK / idle joiners)"),
    )


def _text_modes():
    return (
        "%s\n\n"
        "🎻 %s — %s\n"
        "🚀 %s — %s\n"
        "🐉 %s — %s\n"
        "🌈 %s — %s\n"
        "✍️ %s — %s\n"
        "💀 %s — %s\n"
        "🧩 %s — %s\n\n"
        "<i>%s</i>"
    ) % (
        menu_title_bar("🎮", _("Game modes")),
        menu_heading_bold(_("Classic")),
        _("Standard deck; no auto-skip."),
        menu_heading_bold(_("Sanic (fast)")),
        _("Standard deck; auto-skip if a player is too slow."),
        menu_heading_bold(_("Wild")),
        _("Extra special cards; fewer number cards."),
        menu_heading_bold(_("Rainbow")),
        _("Classic UNO expanded with Purple, Orange, Draw Eight, and Rainbow power cards."),
        menu_heading_bold(_("Text")),
        _("Same rules; card names as text instead of stickers."),
        menu_heading_bold(_("Sudden Death")),
        _("Classic rules but game ends when first player wins (enhanced points)."),
        menu_heading_bold(_("Team")),
        _("Use /teamnew to create Team UNO (2v2 or 3v3)."),
        _("The host chooses the mode from the inline menu before the game starts."),
    )


def _text_source():
    head = menu_title_bar("✦", _("License & source"))
    body = _(
        "Free software (AGPL). Details and links:\n%(url)s\n\n"
        "Maintained by %(owner)s (%(owner_at)s)."
    ) % {
        "url": _SOURCE_CODE_URL,
        "owner": _BOT_OWNER_NAME,
        "owner_at": _BOT_OWNER_AT,
    }
    attr = (
        menu_heading_bold(_("Attributions"))
        + "\n"
        + _(
            'Draw icon by <a href="http://www.faithtoken.com/">Faithtoken</a>\n'
            'Pass icon by <a href="http://delapouite.com/">Delapouite</a>\n'
            "Originals on http://game-icons.net · Icons edited by ɳick"
        )
    )
    return "%s\n\n%s\n\n%s" % (head, body, attr)


def _text_news():
    return "%s\n\n%s" % (
        menu_title_bar("✨", _("Support & updates")),
        _("Official channel:\n%(url)s") % {"url": _SUPPORT_UPDATES_URL},
    )


def _format_stats_lines(user_id):
    return stats_service.format_stats_menu_lines(user_id)


async def send_private_menu(message: Message, bot) -> None:
    kb = _main_menu_keyboard()
    bot_u = await get_bot_username(bot)
    await send_message(
        bot,
        message.chat.id,
        text=_welcome_html(bot_u),
        parse_mode=ParseMode.HTML,
        reply_markup=kb,
        disable_web_page_preview=True,
    )
    await send_promotion(bot, message.chat.id)


@router.message(Command("help"))
async def help_handler(message: Message, bot) -> None:
    if message.chat.type != "private":
        bot_u = await get_bot_username(bot)
        await send_message(
            bot,
            message.chat.id,
            text=_("Open a private chat with me for the full guide and menu."),
            reply_markup=markup(
                [
                    [
                        btn_url(
                            _("Open guide"),
                            "https://t.me/%s?start=help" % bot_u,
                            "primary",
                            icon_role="p14",
                        )
                    ]
                ]
            ),
        )
        return
    await send_private_menu(message, bot)


@router.callback_query(F.data.startswith("m|"))
async def menu_callback(query: CallbackQuery, bot) -> None:
    await answer_callback_query_safe(query)
    data = query.data or ""
    bot_username = await get_bot_username(bot)

    if data == "m|0":
        await safe_edit_message_text(
            query, _welcome_html(bot_username), _main_menu_keyboard()
        )
        return

    if data == "m|h":
        await safe_edit_message_text(
            query,
            menu_title_bar("✨", _("Choose a topic")),
            _help_submenu_keyboard(),
        )
        return

    if data == "m|h1":
        kb = markup([[btn_callback(smallcaps(_("« How to play")), "m|h", "default", icon_role="p13")]])
        await safe_edit_message_text(query, _text_help_quick(bot_username), kb)
        return

    if data == "m|h2":
        kb = markup([[btn_callback(smallcaps(_("« How to play")), "m|h", "default", icon_role="p13")]])
        await safe_edit_message_text(query, _text_help_inline(bot_username), kb)
        return

    if data == "m|h3":
        kb = markup([[btn_callback(smallcaps(_("« How to play")), "m|h", "default", icon_role="p13")]])
        await safe_edit_message_text(query, _text_help_commands(), kb)
        return

    if data == "m|h4":
        kb = markup([[btn_callback(smallcaps(_("« How to play")), "m|h", "default", icon_role="p13")]])
        await safe_edit_message_text(query, _text_help_host(), kb)
        return

    if data == "m|modes":
        await safe_edit_message_text(query, _text_modes(), _footer_menu())
        return

    if data == "m|src":
        await safe_edit_message_text(
            query,
            "%s\n\n%s"
            % (
                menu_title_bar("✦", _("Source")),
                _("This bot is AGPL software. Use <code>/source</code> for the full notice and credits."),
            ),
            _footer_menu(),
        )
        return

    if data == "m|news":
        await safe_edit_message_text(
            query,
            _text_news(),
            _footer_menu(),
        )
        return



@router.message(Command("modes"))
async def modes_cmd(message: Message, bot) -> None:
    await send_message(
        bot,
        message.chat.id,
        text=_text_modes(),
        parse_mode=ParseMode.HTML,
        reply_markup=_footer_menu(),
        disable_web_page_preview=True,
    )


@router.message(Command("source"))
async def source_cmd(message: Message, bot) -> None:
    await send_message(
        bot,
        message.chat.id,
        text=_text_source(),
        parse_mode=ParseMode.HTML,
        reply_markup=_footer_menu(),
        disable_web_page_preview=True,
    )


@router.message(Command("news"))
async def news_cmd(message: Message, bot) -> None:
    await send_message(
        bot,
        message.chat.id,
        text=_text_news(),
        parse_mode=ParseMode.HTML,
        reply_markup=_footer_menu(),
        disable_web_page_preview=True,
    )


@router.message(Command("stats"))
async def stats_cmd(message: Message, bot) -> None:
    user = message.from_user
    body = _format_stats_lines(user.id)
    await send_message(
        bot,
        message.chat.id,
        text="%s\n\n%s" % (menu_title_bar("📊", _("Your statistics")), body),
        parse_mode=ParseMode.HTML,
        reply_markup=_footer_menu(),
    )
