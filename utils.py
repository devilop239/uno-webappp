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

"""Sync helpers shared by game logic and handlers (no Telegram client here)."""

import html
import logging

from internationalization import _, __

logger = logging.getLogger(__name__)


def list_subtract(list1, list2):
    """Subtract list2 from list1 and return the sorted result."""
    list1 = list1.copy()
    for x in list2:
        list1.remove(x)
    return list(sorted(list1))


def sorted_hand_cards(player):
    """Stable hand order for inline card ids (must match add_card / do_play_card)."""
    return sorted(player.cards, key=str)


def card_from_inline_stem(player, stem: str):
    """
    Resolve a card from an inline result stem.
    Uses indexed ids (h0, h1, …) when the hand has duplicate card types.
    Returns None for blocked-only stems.
    """
    import deck.card as card_mod

    if stem.startswith("bh") and stem[2:].isdigit():
        return None
    if stem.startswith("blocked_"):
        return None
    if stem.startswith("h") and len(stem) > 1 and stem[1:].isdigit():
        idx = int(stem[1:])
        hand = sorted_hand_cards(player)
        if 0 <= idx < len(hand):
            return hand[idx]
    return card_mod.from_str(stem)


def display_name(user):
    """Player label with @username when available (logs / legacy)."""
    user_name = user.first_name
    if user.username:
        user_name += " (@%s)" % user.username
    return user_name


def display_name_label(user) -> str:
    """Display name only — no @username (buttons, inline titles)."""
    raw = getattr(user, "first_name", None) or getattr(user, "username", None) or "Player"
    return str(raw).strip() or "Player"


def display_name_html(user) -> str:
    """
    Player label for ParseMode.HTML: clickable name (tg://user?id=…) with bold + smallcaps,
    without appending (@username).
    """
    from ui.text_style import smallcaps

    uid = getattr(user, "id", None)
    if uid is None:
        uid = 0
    raw = getattr(user, "first_name", None) or getattr(user, "username", None) or "Player"
    raw = str(raw).strip() or "Player"
    styled = smallcaps(raw)
    safe = html.escape(styled, quote=False)
    return '<a href="tg://user?id=%d"><b>%s</b></a>' % (int(uid), safe)


# Twemoji CDN thumbnails for inline color picker (Telegram often fails on 💙💚💛 as title icons).
_COLOR_INLINE_THUMB_URLS = {
    "r": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/2764.png",
    "b": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f499.png",
    "g": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f49a.png",
    "y": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f49b.png",
    "p": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f49c.png",
    "o": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f9e1.png",
}


def color_inline_thumbnail_url(color: str) -> str | None:
    """HTTPS thumb for InlineQueryResultArticle (colored heart per UNO color)."""
    return _COLOR_INLINE_THUMB_URLS.get(color)


def display_color_name(color: str) -> str:
    """Localized color name without emoji (for inline titles)."""
    if color == "r":
        return _("Red")
    if color == "b":
        return _("Blue")
    if color == "g":
        return _("Green")
    if color == "y":
        return _("Yellow")
    if color == "p":
        return _("Purple")
    if color == "o":
        return _("Orange")
    return color


def inline_color_choice_title(color: str) -> str:
    """Inline result title: colored heart + smallcaps name."""
    import deck.card as c
    from ui.text_style import inline_label

    emoji = c.COLOR_ICONS.get(color, "")
    return "%s %s" % (emoji, inline_label(display_color_name(color)))


def display_color(color):
    """Map color code to localized name."""
    import deck.card as c

    emoji = c.COLOR_ICONS.get(color, "")
    if color == "r":
        return _("{emoji} Red").format(emoji=emoji)
    if color == "b":
        return _("{emoji} Blue").format(emoji=emoji)
    if color == "g":
        return _("{emoji} Green").format(emoji=emoji)
    if color == "y":
        return _("{emoji} Yellow").format(emoji=emoji)
    if color == "p":
        return _("{emoji} Purple").format(emoji=emoji)
    if color == "o":
        return _("{emoji} Orange").format(emoji=emoji)
    return color


def display_color_group(color, game):
    """Localized color name using the game's translation mode."""
    import deck.card as c

    emoji = c.COLOR_ICONS.get(color, "")
    if color == "r":
        return __("{emoji} Red", game.translate).format(emoji=emoji)
    if color == "b":
        return __("{emoji} Blue", game.translate).format(emoji=emoji)
    if color == "g":
        return __("{emoji} Green", game.translate).format(emoji=emoji)
    if color == "y":
        return __("{emoji} Yellow", game.translate).format(emoji=emoji)
    if color == "p":
        return __("{emoji} Purple", game.translate).format(emoji=emoji)
    if color == "o":
        return __("{emoji} Orange", game.translate).format(emoji=emoji)
    return color


def game_is_running(game):
    from shared_vars import gm
    return game in gm.chatid_games.get(game.chat.id, list())


def user_is_creator(user, game):
    return user.id in game.owner
