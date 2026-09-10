"""Turn prompts — NO MERCY uses the same @bot inline flow as other modes."""
from __future__ import annotations

from aiogram.enums import ParseMode

from ui.inline_buttons import btn_switch_current_chat, markup
from no_mercy.text_style import sc
from tg.helpers import send_game_turn_prompt
from utils import _


def _default_turn_markup(game=None):
    label = _("Make your choice!")
    if game is not None and getattr(game, "mode", None) == "no_mercy":
        label = sc(label)
    return markup([[btn_switch_current_chat(label, "", "success")]])


async def send_turn_prompt_compat(
    bot,
    game,
    classic_text: str,
    classic_reply_markup=None,
    **kwargs,
) -> None:
    """Same turn UI as classic modes: short message + switch-to-inline button."""
    if classic_reply_markup is None:
        classic_reply_markup = _default_turn_markup(game)

    await send_game_turn_prompt(
        bot,
        game,
        classic_text,
        parse_mode=kwargs.pop("parse_mode", ParseMode.HTML),
        reply_markup=classic_reply_markup,
        **kwargs,
    )


async def send_mercy_turn_prompt(bot, game, *, header: str | None = None) -> None:
    """Backward-compatible alias — classic inline turn prompt."""
    from utils import display_name_html

    text = header or _("ɴᴇxᴛ ᴘʟᴀʏᴇʀ: {name}").format(
        name=display_name_html(game.current_player.user)
    )
    await send_turn_prompt_compat(bot, game, text)


async def refresh_mercy_prompt(bot, game, **kwargs) -> None:
    """Refresh turn prompt after a pending action (inline-only UI)."""
    from utils import display_name_html

    player = game.current_player
    if player is None:
        return
    text = _("ɴᴇxᴛ ᴘʟᴀʏᴇʀ: {name}").format(name=display_name_html(player.user))
    await send_turn_prompt_compat(bot, game, text)
