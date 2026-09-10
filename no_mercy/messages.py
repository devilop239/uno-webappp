"""NO MERCY group chat announcements."""
from __future__ import annotations

from aiogram.enums import ParseMode

from no_mercy.text_style import sc, sc_bold
from tg.helpers import send_message
from utils import display_name_html


async def announce_stack(bot, game, chat_id: int) -> None:
    n = int(game.draw_counter or 0)
    if n >= 20:
        text = "💀 %s" % sc("STACK IS AT +%d" % n)
    elif n >= 10:
        text = "⚠️ %s" % sc("STACK IS AT +%d" % n)
    else:
        return
    await send_message(bot, chat_id, text=text)


async def announce_chain_bounced(bot, chat_id: int) -> None:
    await send_message(bot, chat_id, text="🔄 %s" % sc("CHAIN BOUNCED BACK!"))


async def announce_eliminated(bot, game, chat_id: int, user) -> None:
    if bot is None:
        return
    await send_message(
        bot,
        chat_id,
        text="💥 %s %s!" % (sc_bold("ELIMINATED FROM NO MERCY"), display_name_html(user)),
        parse_mode=ParseMode.HTML,
    )


async def announce_roulette(bot, chat_id: int) -> None:
    await send_message(bot, chat_id, text="🎰 %s" % sc("ROULETTE ACTIVATED!"))


async def announce_swap(bot, chat_id: int) -> None:
    await send_message(bot, chat_id, text="🔀 %s" % sc("HANDS SWAPPED!"))


async def announce_uno(bot, game, chat_id: int, user) -> None:
    await send_message(
        bot,
        chat_id,
        text="🃏 %s %s!" % (display_name_html(user), sc_bold("HAS UNO")),
        parse_mode=ParseMode.HTML,
    )


async def announce_draw_until_playable(bot, chat_id: int, user, *, drew: int) -> None:
    if drew <= 0:
        return
    if drew == 1:
        resolved = sc("Auto-drew resolved after 1 card")
    else:
        resolved = sc("Auto-drew resolved after %d cards" % drew)
    await send_message(
        bot,
        chat_id,
        text="🃏 %s %s. %s — %s"
        % (
            sc("No playable cards found for"),
            display_name_html(user),
            resolved,
            sc("It's your turn."),
        ),
        parse_mode=ParseMode.HTML,
    )
