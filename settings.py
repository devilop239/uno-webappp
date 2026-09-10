#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# UNO Telegram bot — by demon (@demon12809)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from ui.inline_buttons import btn_callback, markup
from internationalization import _
from services import user_service
from tg.helpers import answer_callback_query_safe, safe_edit_message_text, send_message
from ui.text_style import menu_heading_bold, menu_title_bar, smallcaps

settings_router = Router(name="settings")


def _load_us(user_id):
    return user_service.load_or_create_prefs(user_id)


def settings_keyboard():
    rows = [
        [
            btn_callback(smallcaps(_("Main menu")), "m|0", "default", icon_role="p5")
        ],
    ]
    return markup(rows)

def settings_header_html():
    return "%s\n%s" % (
        menu_title_bar("⚙️", _("Settings")),
        menu_heading_bold(_("Statistics always on")),
    )


async def edit_to_settings_panel(query: CallbackQuery) -> None:
    _load_us(query.from_user.id)
    await safe_edit_message_text(query, settings_header_html(), settings_keyboard())


@settings_router.message(Command("settings"))
async def show_settings(message: Message, bot) -> None:
    chat = message.chat
    if chat.type != "private":
        await send_message(
            bot,
            chat.id,
            text=_("Please open a private chat with the bot for settings."),
        )
        return
    _load_us(message.from_user.id)
    await send_message(
        bot,
        chat.id,
        text=settings_header_html(),
        reply_markup=settings_keyboard(),
        parse_mode=ParseMode.HTML,
    )


@settings_router.callback_query(F.data.startswith("st|"))
async def settings_callback(query: CallbackQuery, bot) -> None:
    user = query.from_user
    data = query.data or ""

    parts = data.split("|")
    action = parts[1] if len(parts) > 1 else ""

    if action == "e":
        user_service.set_stats_enabled(user.id, True)
        await answer_callback_query_safe(
            query, text=_("Statistics are always on."), show_alert=False
        )
        await safe_edit_message_text(query, settings_header_html(), settings_keyboard())
        return

    if action == "d":
        await answer_callback_query_safe(
            query, text=_("Statistics cannot be disabled."), show_alert=False
        )
        user_service.set_stats_enabled(user.id, True)
        await safe_edit_message_text(query, settings_header_html(), settings_keyboard())
        return

    if action == "x":
        await answer_callback_query_safe(query)
        if query.message:
            try:
                await query.message.edit_text(
                    text=_(
                        "Settings closed. Send /settings anytime to open this menu again."
                    ),
                    reply_markup=None,
                )
            except TelegramBadRequest as e:
                if "not modified" not in str(e).lower():
                    raise
        return
