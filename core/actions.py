# -*- coding: utf-8 -*-
"""Game turn actions and execution logic (play card, draw, pass, skip, call bluff)."""

import asyncio
import logging
import random
from typing import Optional, Any

import deck.card as c
from deck.styles import normalize_deck_style
from config import MIN_FAST_TURN_TIME, TIME_REMOVAL_AFTER_SKIP, WAITING_TIME
from errors import (
    CardNotOwnedError,
    DeckEmptyError,
    IllegalCardError,
    InvalidActionError,
    NotEnoughPlayersError,
)
from internationalization import __
from modes.capabilities import supports_bluff_challenge, supports_pass_after_draw
from services import user_service
from services.match_result_service import (
    capture_match_context,
    send_post_match_scoreboard,
)
from services.match_service import increment_cards_played
from ui.inline_buttons import btn_callback, markup
from utils import display_name, display_name_html, game_is_running, card_from_inline_stem

logger = logging.getLogger(__name__)


def _get_gm():
    from shared_vars import gm
    return gm


def _record_play_stats(user) -> None:
    user_service.ensure_user_row(user)
    increment_cards_played(user)


_BLUFF_CHALLENGER_DRAW_LINES = (
    (
        "ʙʀᴀɪɴ ʟᴏꜱᴛ, ᴄᴀʀᴅꜱ ɢᴀɪɴᴇᴅ 😭 {name} ɢʀᴀʙꜱ {number} ᴄᴀʀᴅꜱ",
        "ʙʀᴀɪɴ ʟᴏꜱᴛ, ᴄᴀʀᴅꜱ ɢᴀɪɴᴇᴅ 😭 {name} ɢʀᴀʙꜱ {number} ᴄᴀʀᴅꜱ",
    ),
    (
        "ɴɪᴄᴇ ᴛʀʏ 😭 {name} ꜱᴛɪʟʟ ᴇɴᴅꜱ ᴜᴘ ᴡɪᴛʜ {number} ᴄᴀʀᴅꜱ",
        "ɴɪᴄᴇ ᴛʀʏ 😭 {name} ꜱᴛɪʟʟ ᴇɴᴅꜱ ᴜᴘ ᴡɪᴛʜ {number} ᴄᴀʀᴅꜱ",
    ),
    (
        "ʙʀᴀɪɴ ʟᴀɢ ᴅᴇᴛᴇᴄᴛᴇᴅ 😶‍🌫️ {name} ᴅʀᴀᴡꜱ {number} ᴄᴀʀᴅꜱ",
        "ʙʀᴀɪɴ ʟᴀɢ ᴅᴇᴛᴇᴄᴛᴇᴅ 😶‍🌫️ {name} ᴅʀᴀᴡꜱ {number} ᴄᴀʀᴅꜱ",
    ),
    (
        "ᴛᴏᴏ ᴍᴜᴄʜ ᴄᴏɴꜰɪᴅᴇɴᴄᴇ 🫣 {name} ɴᴏᴡ ʜᴀꜱ {number} ᴍᴏʀᴇ ᴘʀᴏʙʟᴇᴍꜱ",
        "ᴛᴏᴏ ᴍᴜᴄʜ ᴄᴏɴꜰɪᴅᴇɴᴄᴇ 🫣 {name} ɴᴏᴡ ʜᴀꜱ {number} ᴍᴏʀᴇ ᴘʀᴏʙʟᴇᴍꜱ",
    ),
)

_BLUFF_CALL_FAILED_INNOCENT_LINES = (
    (
        "ᴄᴀʟʟ ꜰᴀɪʟᴇᴅ {name1} ᴅɪᴅɴ’t ʙʟᴜꜰꜰ, {name2} ɢᴇᴛꜱ {number} ᴄᴀʀᴅꜱ",
        "ᴄᴀʟʟ ꜰᴀɪʟᴇᴅ {name1} ᴅɪᴅɴ’t ʙʟᴜꜰꜰ, {name2} ɢᴇᴛꜱ {number} ᴄᴀʀᴅꜱ",
    ),
    (
        "ᴄᴀʟʟ ꜰᴀɪʟᴇᴅ 😭 {name1} ᴡᴀꜱ ɪɴɴᴏᴄᴇɴᴛ, {name2} ɢᴇᴛꜱ {number} ᴄᴀʀᴅꜱ",
        "ᴄᴀʟʟ ꜰᴀɪʟᴇᴅ 😭 {name1} ᴡᴀꜱ ɪɴɴᴏᴄᴇɴᴛ, {name2} ɢᴇᴛꜱ {number} ᴄᴀʀᴅꜱ",
    ),
    (
        "ᴄᴀʟʟ ᴅᴇɴɪᴇᴅ 🚫 {name1} ᴡᴀꜱɴ’t ʙʟᴜꜰꜰɪɴɢ, {name2} ɢᴇᴛꜱ {number} ᴄᴀʀᴅꜱ",
        "ᴄᴀʟʟ ᴅᴇɴɪᴇᴅ 🚫 {name1} ᴡᴀꜱɴ’t ʙʟᴜꜰꜰɪɴɢ, {name2} ɢᴇᴛꜱ {number} ᴄᴀʀᴅꜱ",
    ),
    (
        "ʙʀᴀɪɴ ʟᴀɢ 😶‍🌫️ {name1} ᴘʟᴀʏᴇᴅ ᴄʟᴇᴀɴ, {name2} ᴛᴀᴋᴇꜱ {number} ᴄᴀʀᴅꜱ",
        "ʙʀᴀɪɴ ʟᴀɢ 😶‍🌫️ {name1} ᴘʟᴀʏᴇᴅ ᴄʟᴇᴀɴ, {name2} ᴛᴀᴋᴇꜱ {number} ᴄᴀʀᴅꜱ",
    ),
)


def cancel_fast_countdown(game):
    """Cancel pending auto-skip task (fast mode)."""
    task = getattr(game, "countdown_task", None)
    if task is not None and not task.done():
        task.cancel()
    game.countdown_task = None


async def do_skip(bot: Optional[Any], player, from_scheduled_job=False):
    """Skip the current player's turn or remove player if out of time."""
    game = player.game
    if not game_is_running(game):
        return
    chat = game.chat
    skipped_player = game.current_player
    next_player = game.current_player.next

    if from_scheduled_job and skipped_player.user.id != player.user.id:
        logger.debug(
            "do_skip: stale task ignored (current=%s, scheduled_for=%s)",
            skipped_player.user.id,
            player.user.id,
        )
        return

    if bot:
        try:
            from tg.helpers import delete_game_turn_prompt_safe
            await delete_game_turn_prompt_safe(bot, game)
        except Exception as e:
            logger.debug("Failed deleting turn prompt safe: %s", e)

    if skipped_player.waiting_time > 0:
        skipped_player.anti_cheat += 1
        skipped_player.waiting_time -= TIME_REMOVAL_AFTER_SKIP
        if skipped_player.waiting_time < 0:
            skipped_player.waiting_time = 0

        try:
            skipped_player.draw()
        except DeckEmptyError:
            pass

        n = skipped_player.waiting_time
        if bot and chat:
            try:
                from tg.helpers import send_message
                from aiogram.enums import ParseMode
                await send_message(
                    bot,
                    chat.id,
                    text=__(
                        "Waiting time to skip this player has "
                        "been reduced to {time} seconds.\n"
                        "ɴᴇxᴛ ᴘʟᴀʏᴇʀ: {name}",
                        multi=game.translate,
                    ).format(time=n, name=display_name_html(next_player.user)),
                    parse_mode=ParseMode.HTML,
                )
            except Exception as e:
                logger.debug("Failed sending skip msg: %s", e)

        logger.info("%s was skipped (penalty draw).", display_name(skipped_player.user))
        game.turn()
        await start_player_countdown(bot, game)

    else:
        try:
            _get_gm().leave_game(skipped_player.user, chat)
            if bot and chat:
                try:
                    from tg.helpers import send_message
                    from aiogram.enums import ParseMode
                    await send_message(
                        bot,
                        chat.id,
                        text=__(
                            "{name1} ran out of time "
                            "and has been removed from the game!\n"
                            "ɴᴇxᴛ ᴘʟᴀʏᴇʀ: {name2}",
                            multi=game.translate,
                        ).format(
                            name1=display_name_html(skipped_player.user),
                            name2=display_name_html(next_player.user),
                        ),
                        parse_mode=ParseMode.HTML,
                    )
                except Exception as e:
                    logger.debug("Failed sending timeout removal msg: %s", e)

            logger.info("%s removed (out of time).", display_name(skipped_player.user))
            await start_player_countdown(bot, game)

        except NotEnoughPlayersError:
            if bot and chat:
                try:
                    from tg.helpers import delete_game_turn_prompt_safe, send_message
                    from aiogram.enums import ParseMode
                    await delete_game_turn_prompt_safe(bot, game)
                    await send_message(
                        bot,
                        chat.id,
                        text=__(
                            "{name} ran out of time "
                            "and has been removed from the game!\n"
                            "The game ended.",
                            multi=game.translate,
                        ).format(name=display_name_html(skipped_player.user)),
                        parse_mode=ParseMode.HTML,
                    )
                except Exception as e:
                    logger.debug("Failed sending end game msg: %s", e)

            ctx = capture_match_context(game, fallback_user=skipped_player.user)
            _get_gm().end_game(
                chat,
                skipped_player.user,
                reason="abandoned_timeout",
                abandon_user_id=skipped_player.user.id,
            )
            if bot and chat:
                try:
                    await send_post_match_scoreboard(bot, chat.id, ctx)
                except Exception as e:
                    logger.debug("Failed sending post match scoreboard: %s", e)


async def do_play_card(bot: Optional[Any], player, result_id: str):
    """Play the selected card and handle game outcome / transitions."""
    game = player.game
    card = card_from_inline_stem(player, result_id)
    if card is None:
        raise CardNotOwnedError("The selected card could not be found")
    if card not in player.cards:
        logger.warning(
            "Rejected invalid play payload user_id=%s card=%s",
            getattr(player.user, "id", None),
            result_id,
        )
        raise CardNotOwnedError("The selected card is not in the player's hand")

    if not player._card_playable(card):
        raise IllegalCardError("The selected card cannot be played now")

    if game.mode == "no_mercy":
        from no_mercy.game_state import blocks_normal_play
        from no_mercy.elimination import enforce_elimination_threshold
        from no_mercy.state import is_eliminated_uid, should_eliminate

        if is_eliminated_uid(game, player.user.id):
            return
        if should_eliminate(len(player.cards)):
            if await enforce_elimination_threshold(bot, player):
                return

        if blocks_normal_play(game):
            logger.info(
                "Rejected play during pending choice user_id=%s card=%s",
                getattr(player.user, "id", None),
                result_id,
            )
            return

    player.play(card)
    chat = game.chat
    user = player.user

    if game.mode == "no_mercy":
        asyncio.create_task(
            asyncio.to_thread(_record_play_stats, user),
            name="uno-nm-play-stats",
        )
    else:
        _record_play_stats(user)

    if game.mode == "no_mercy":
        from no_mercy.actions_hook import after_play_card
        if await after_play_card(bot, player, card) == "stop":
            return


async def do_pass(bot: Optional[Any], player):
    """Pass after drawing a normal card during the current turn."""
    game = player.game
    chat = game.chat
    user = player.user
    if not player.drew:
        raise InvalidActionError("You must draw before passing")
    if game.draw_counter:
        raise InvalidActionError("The draw penalty must be resolved before passing")
    game.turn()

    if game.choosing_color and bot and chat:
        try:
            from tg.helpers import send_message
            await send_message(
                bot,
                chat.id,
                text=__("ᴘʟᴇᴀꜱᴇ ᴄʜᴏᴏꜱᴇ ᴀ ᴄᴏʟᴏʀ 🎨", multi=game.translate),
            )
        except Exception as e:
            logger.debug("Failed sending choose color prompt: %s", e)

    if len(player.cards) == 1 and game.mode != "no_mercy" and bot and chat:
        try:
            from tg.helpers import send_message
            await send_message(bot, chat.id, text="UNO!")
        except Exception as e:
            logger.debug("Failed sending UNO call: %s", e)

    if len(player.cards) == 0:
        if game.mode == "sudden_death":
            if bot and chat:
                try:
                    from tg.helpers import send_message
                    from aiogram.enums import ParseMode
                    await send_message(
                        bot,
                        chat.id,
                        text=__("💀 SUDDEN DEATH! {name} wins the game!", multi=game.translate).format(
                            name=display_name_html(user)
                        ),
                        parse_mode=ParseMode.HTML,
                    )
                except Exception as e:
                    logger.debug("Failed sending sudden death win message: %s", e)
            game.finish_order.append(user.id)
            game.players_won += 1
            ctx = capture_match_context(game, fallback_user=user)
            _get_gm().end_game(chat, user, reason="completed_sudden_death")
            if bot and chat:
                try:
                    await send_post_match_scoreboard(bot, chat.id, ctx)
                except Exception as e:
                    logger.debug("Failed sending sudden death scoreboard: %s", e)
            return

        if bot and chat:
            try:
                from tg.helpers import send_message
                from aiogram.enums import ParseMode
                await send_message(
                    bot,
                    chat.id,
                    text=__("{name} won!", multi=game.translate).format(
                        name=display_name_html(user)
                    ),
                    parse_mode=ParseMode.HTML,
                )
            except Exception as e:
                logger.debug("Failed sending win msg: %s", e)

        game.finish_order.append(user.id)
        game.players_won += 1

        try:
            _get_gm().leave_game(user, chat)
        except NotEnoughPlayersError:
            if bot and chat:
                try:
                    from tg.helpers import send_message
                    await send_message(
                        bot,
                        chat.id,
                        text=__("ɢᴀᴍᴇ ᴇɴᴅᴇᴅ!", multi=game.translate),
                    )
                except Exception as e:
                    logger.debug("Failed sending game ended msg: %s", e)

            ctx = capture_match_context(game, fallback_user=user)
            _get_gm().end_game(chat, user, reason="completed")
            if bot and chat:
                try:
                    await send_post_match_scoreboard(bot, chat.id, ctx)
                except Exception as e:
                    logger.debug("Failed sending post match scoreboard: %s", e)


async def do_draw(bot: Optional[Any], player):
    """Draw card(s) for player."""
    game = player.game
    draw_counter_before = game.draw_counter
    if draw_counter_before == 0 and player.drew:
        if game.mode != "no_mercy":
            logger.info(
                "do_draw ignored: player already drew this turn user_id=%s",
                getattr(player.user, "id", None),
            )
            raise InvalidActionError("You have already drawn this turn")
        from no_mercy.playability import has_any_playable

        if has_any_playable(player):
            logger.info(
                "do_draw ignored: mercy player must play drawn card user_id=%s",
                getattr(player.user, "id", None),
            )
            return

    if game.mode == "no_mercy":
        from no_mercy.actions_hook import after_draw
        from no_mercy.elimination import enforce_elimination_threshold
        from no_mercy.forced_draw import mercy_draw_turn
        from no_mercy.messages import announce_draw_until_playable
        from no_mercy.state import is_eliminated_uid, should_eliminate

        if is_eliminated_uid(game, player.user.id):
            return
        if should_eliminate(len(player.cards)):
            if await enforce_elimination_threshold(bot, player):
                return

        try:
            if draw_counter_before > 0:
                player.draw()
                drew = draw_counter_before
            else:
                drew = mercy_draw_turn(player)
        except DeckEmptyError:
            if bot and game.chat:
                try:
                    from tg.helpers import send_message
                    await send_message(
                        bot,
                        game.chat.id,
                        text=__(
                            "There are no more cards in the deck.",
                            multi=game.translate,
                        ),
                    )
                except Exception as e:
                    logger.debug("Failed sending empty deck msg: %s", e)
            return

        if draw_counter_before > 0:
            game.turn()
        elif drew > 1 and bot and game.chat:
            await announce_draw_until_playable(
                bot, game.chat.id, player.user, drew=drew
            )
        await after_draw(
            bot,
            player,
            stack_penalty=draw_counter_before > 0,
        )
        return

    try:
        player.draw()
    except DeckEmptyError:
        if bot and game.chat:
            try:
                from tg.helpers import send_message
                await send_message(
                    bot,
                    player.game.chat.id,
                    text=__(
                        "There are no more cards in the deck.",
                        multi=game.translate,
                    ),
                )
            except Exception as e:
                logger.debug("Failed sending deck empty msg: %s", e)
        return

    if (
        game.last_card.value == c.DRAW_TWO
        or game.last_card.special in (c.DRAW_FOUR, c.DRAW_EIGHT, c.RAINBOW_MONSTER)
    ) and draw_counter_before > 0:
        if game.last_card.special in (c.DRAW_FOUR, c.DRAW_EIGHT):
            game.last_draw_special_challengeable = False
        game.turn()


async def do_call_bluff(bot: Optional[Any], player):
    """Challenge player draw special bluff."""
    game = player.game
    chat = game.chat

    if not supports_bluff_challenge(game):
        raise InvalidActionError("Bluff challenges are not enabled for this mode")

    last = game.last_card
    if last.special not in (c.DRAW_FOUR, c.DRAW_EIGHT):
        raise InvalidActionError("There is no draw card to challenge")
    if not getattr(game, "last_draw_special_challengeable", False):
        # A stale Telegram/WebApp action can arrive after the challenge window
        # has already been resolved. Treat it as a no-op instead of surfacing
        # an exception to the caller.
        logger.info(
            "do_call_bluff ignored: challenge window closed user_id=%s",
            getattr(player.user, "id", None),
        )
        return

    penalty = 4 if last.special == c.DRAW_FOUR else 8
    pending_total = game.draw_counter if game.draw_counter > 0 else penalty

    if getattr(game, "last_bluffable_draw_special", False):
        singular, plural = random.choice(_BLUFF_CHALLENGER_DRAW_LINES)
        if bot and chat:
            try:
                from tg.helpers import send_message
                from aiogram.enums import ParseMode
                await send_message(
                    bot,
                    chat.id,
                    text=__(
                        singular,
                        plural,
                        pending_total,
                        multi=game.translate,
                    ).format(
                        number=pending_total,
                        name=display_name_html(player.prev.user),
                    ),
                    parse_mode=ParseMode.HTML,
                )
            except Exception as e:
                logger.debug("Failed sending bluff win msg: %s", e)

        try:
            game.draw_counter = pending_total
            player.prev.draw()
        except DeckEmptyError:
            if bot and chat:
                try:
                    from tg.helpers import send_message
                    await send_message(
                        bot,
                        player.game.chat.id,
                        text=__(
                            "There are no more cards in the deck.",
                            multi=game.translate,
                        ),
                    )
                except Exception as e:
                    logger.debug("Failed sending empty deck msg: %s", e)

    else:
        fail_total = pending_total + 2
        game.draw_counter = fail_total
        singular, plural = random.choice(_BLUFF_CALL_FAILED_INNOCENT_LINES)
        if bot and chat:
            try:
                from tg.helpers import send_message
                from aiogram.enums import ParseMode
                await send_message(
                    bot,
                    chat.id,
                    text=__(
                        singular,
                        plural,
                        fail_total,
                        multi=game.translate,
                    ).format(
                        name1=display_name_html(player.prev.user),
                        name2=display_name_html(player.user),
                        number=fail_total,
                    ),
                    parse_mode=ParseMode.HTML,
                )
            except Exception as e:
                logger.debug("Failed sending bluff fail msg: %s", e)
        try:
            player.draw()
        except DeckEmptyError:
            if bot and chat:
                try:
                    from tg.helpers import send_message
                    await send_message(
                        bot,
                        player.game.chat.id,
                        text=__(
                            "There are no more cards in the deck.",
                            multi=game.translate,
                        ),
                    )
                except Exception as e:
                    logger.debug("Failed sending empty deck msg: %s", e)

    game.last_bluffable_draw_special = False
    game.last_draw_special_challengeable = False
    game.turn()


async def _countdown_then_skip(bot: Optional[Any], player, delay: float):
    await asyncio.sleep(delay)
    game = player.game
    if game_is_running(game):
        await do_skip(bot, player, from_scheduled_job=True)


async def start_player_countdown(bot: Optional[Any], game):
    if game.mode != "fast":
        return
    player = game.current_player
    wait = player.waiting_time
    if wait < MIN_FAST_TURN_TIME:
        wait = MIN_FAST_TURN_TIME
    cancel_fast_countdown(game)
    task = asyncio.create_task(
        _countdown_then_skip(bot, player, float(wait)),
        name="uno-fast-countdown",
    )
    game.countdown_task = task
    logger.info(
        "Started countdown for player: %s. %s seconds.",
        display_name(player.user),
        wait,
    )


async def reset_waiting_time(bot: Optional[Any], player) -> None:
    """Reset waiting time for player."""
    if player.game.mode == "no_mercy":
        return
    chat = player.game.chat
    if player.waiting_time < WAITING_TIME:
        player.waiting_time = WAITING_TIME
        if bot and chat:
            try:
                from tg.helpers import send_message
                from aiogram.enums import ParseMode
                await send_message(
                    bot,
                    chat.id,
                    text=__(
                        "Waiting time for {name} has been reset to {time} seconds",
                        multi=player.game.translate,
                    ).format(name=display_name_html(player.user), time=WAITING_TIME),
                    parse_mode=ParseMode.HTML,
                )
            except Exception as e:
                logger.debug("Failed sending reset waiting time msg: %s", e)
