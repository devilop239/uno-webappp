# -*- coding: utf-8 -*-
"""Inline query + chosen result (gameplay via @bot)."""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.enums import ParseMode
from aiogram.types import ChosenInlineResult, InlineQuery
from aiogram.types import InlineQueryResultArticle, InlineQueryResultCachedSticker as Sticker

import deck.card as c
from core.actions import (
    cancel_fast_countdown,
    do_call_bluff,
    do_draw,
    do_play_card,
    reset_waiting_time,
    start_player_countdown,
)
from inline_buttons import btn_switch_current_chat, markup
from internationalization import _, __
from internationalization import (
    pop_locale_stack_n,
    push_game_locales_for_user_chat,
    user_chat_for_chosen_inline_result,
)
from utils import color_inline_thumbnail_url, display_color_group, inline_color_choice_title
from results import (
    add_call_bluff,
    add_card,
    add_choose_color,
    add_mercy_bonus_discard,
    add_mercy_choose_opponent,
    add_draw,
    add_gameinfo,
    add_mode_classic,
    add_mode_fast,
    add_mode_rainbow,
    add_mode_no_mercy,
    add_mode_sudden_death,
    add_mode_text,
    add_mode_team,
    add_mode_wild,
    add_no_game,
    add_no_mercy_turn_cards,
    add_not_started,
    add_other_cards,
    add_pass,
)
from handlers.private_mode import sync_private_boards
from loggers import format_user, schedule_audit_telegram
from services.private_battle_service import private_battles
from modes.capabilities import supports_bluff_challenge
from shared_vars import gm
from tg.helpers import (
    answer_inline_query,
    delete_game_turn_prompt_safe,
    send_game_turn_prompt,
    send_message,
    user_is_creator_or_admin_aiogram,
)
from ui.text_style import inline_label, premium_input_text
from utils import display_name_html, game_is_running, user_is_creator

logger = logging.getLogger(__name__)

router = Router(name="inline")


def _parse_inline_result_id(raw):
    if raw is None or not str(raw).strip():
        raise ValueError("empty inline result_id")

    parts = str(raw).split(":")
    if len(parts) >= 5:
        try:
            chat_id = int(parts[-1])
            mode = parts[-2]
            int(parts[-3])  # ui-state fingerprint (not validated on choose)
            anti_cheat = int(parts[-4])
            stem = ":".join(parts[:-4])
            return stem, anti_cheat, chat_id, mode
        except ValueError:
            pass

    if len(parts) >= 4:
        try:
            chat_id = int(parts[-1])
            int(parts[-2])  # ui-state fingerprint (not validated on choose)
            anti_cheat = int(parts[-3])
            stem = ":".join(parts[:-3])
            return stem, anti_cheat, chat_id, None
        except ValueError:
            pass

    if len(parts) >= 3:
        try:
            chat_id = int(parts[-1])
            anti_cheat = int(parts[-2])
            stem = ":".join(parts[:-2])
            return stem, anti_cheat, chat_id, None
        except ValueError:
            pass

    if len(parts) == 2:
        try:
            return parts[0], int(parts[1]), None, None
        except ValueError:
            pass

    raise ValueError("invalid inline result_id")


def _inline_ui_state(game) -> int:
    """Bit flags embedded in inline ids so menu type never reuses stale ids."""
    state = 0
    if game.choosing_color:
        state |= 1
    if getattr(game, "mercy_pending_swap", False):
        state |= 2
    rou = getattr(game, "mercy_pending_roulette", None)
    if rou == "target":
        state |= 4
    elif rou == "color":
        state |= 8
    if getattr(game, "mercy_extra_discard_pending", False):
        state |= 16
    return state


def _inline_result_id(base_id: str, player, game) -> str:
    mode = getattr(game, "mode", None) or "classic"
    return f"{base_id}:{player.anti_cheat}:{_inline_ui_state(game)}:{mode}:{game.chat.id}"


def _private_can_challenge_draw_four(game, user_id: int) -> bool:
    state = game.draw_four_state
    return bool(
        game.status == "active"
        and state is not None
        and not state.resolved
        and user_id == state.challenger_id
        and user_id == game.current_turn_user_id
        and game.choosing_color_for is None
        and int(game.draw_penalty or 0) == 4
    )


def _private_can_draw(game, user_id: int) -> bool:
    if game.status != "active":
        return False
    if user_id != game.current_turn_user_id:
        return False
    if game.choosing_color_for is not None:
        return False

    # +4 challenge window: challenger may choose challenge or draw (accept).
    state = game.draw_four_state
    if (
        state is not None
        and not state.resolved
        and user_id == state.challenger_id
        and int(game.draw_penalty or 0) == 4
    ):
        return True

    # Standard UNO flow: once the player has drawn a normal card this turn,
    # draw should not be offered again (player can play or pass).
    if int(game.draw_penalty or 0) > 0:
        return True
    return not bool(game.drew_this_turn)


def _private_can_pass(game, user_id: int) -> bool:
    if game.status != "active":
        return False
    if user_id != game.current_turn_user_id:
        return False
    if game.choosing_color_for is not None:
        return False
    if game.draw_four_state and not game.draw_four_state.resolved and user_id == game.draw_four_state.challenger_id:
        return False
    return bool(game.drew_this_turn)


def _add_private_inline_results(results, game, user_id: int):
    hand = list(game.hands.get(user_id, []))
    is_turn = user_id == game.current_turn_user_id
    is_color_choice = game.choosing_color_for == user_id
    has_pending_draw_four_challenge = _private_can_challenge_draw_four(game, user_id)

    if game.status == "pending_start":
        results.append(
            Sticker(
                id="pv|wait",
                sticker_file_id=c.STICKERS["option_info"],
                input_message_content=premium_input_text(
                    _("Private battle is waiting for host to start.")
                ),
            )
        )
        return

    if not is_turn and not is_color_choice:
        results.append(
            Sticker(
                id="pv|wait_turn",
                sticker_file_id=c.STICKERS["option_info"],
                input_message_content=premium_input_text(
                    _("Opponent is taking their turn.")
                ),
            )
        )

    if is_color_choice:
        for color in c.COLORS:
            thumb = color_inline_thumbnail_url(color)
            kwargs = dict(
                id=f"pv|color|{color}",
                title=inline_color_choice_title(color),
                description=inline_label(_("Choose a color to continue your move.")),
                input_message_content=premium_input_text(
                    display_color_group(color, game)
                ),
            )
            if thumb:
                kwargs["thumbnail_url"] = thumb
                kwargs["thumbnail_width"] = 48
                kwargs["thumbnail_height"] = 48
            results.append(InlineQueryResultArticle(**kwargs))

    if has_pending_draw_four_challenge:
        results.append(
            Sticker(
                id="pv|challenge",
                sticker_file_id=c.STICKERS["option_bluff"],
                input_message_content=premium_input_text(
                    _("I'm calling your bluff!")
                ),
            )
        )

    if _private_can_draw(game, user_id):
        # Match group inline `add_draw`: show how many cards this draw will take (+2/+4 stacks).
        if has_pending_draw_four_challenge:
            n_draw = game.draw_penalty if game.draw_penalty > 0 else 4
            draw_label = _(
                "Accept +4 and draw {number} card",
                "Accept +4 and draw {number} cards",
                n_draw,
            ).format(number=n_draw)
        else:
            n_draw = game.draw_penalty if game.draw_penalty > 0 else 1
            draw_label = _(
                "ᴘɪᴄᴋɪɴɢ {number} ᴄᴀʀᴅꜱ",
                "ᴘɪᴄᴋɪɴɢ {number} ᴄᴀʀᴅꜱ",
                n_draw,
            ).format(number=n_draw)

        results.append(
            Sticker(
                id="pv|draw",
                sticker_file_id=c.STICKERS["option_draw"],
                input_message_content=premium_input_text(draw_label),
            )
        )

    if _private_can_pass(game, user_id):
        results.append(
            Sticker(
                id="pv|pass",
                sticker_file_id=c.STICKERS["option_pass"],
                input_message_content=premium_input_text(_("Pass turn")),
            )
        )

    playable_ids = set()
    if game.choosing_color_for is None:
        for card_obj in private_battles.playable_hand(game, user_id):
            playable_ids.add(id(card_obj))

    for idx, card_obj in enumerate(hand):
        can_play = (
            is_turn
            and game.choosing_color_for is None
            and not has_pending_draw_four_challenge
            and id(card_obj) in playable_ids
        )

        if can_play:
            results.append(
                Sticker(
                    id=f"pv|play|{idx}",
                    sticker_file_id=c.sticker_for(card_obj, game),
                )
            )
        else:
            results.append(
                Sticker(
                    id=f"pv|blocked|{idx}",
                    sticker_file_id=c.sticker_for(card_obj, game, playable=False),
                    input_message_content=premium_input_text(_("Not playable right now.")),
                )
            )


@router.inline_query()
async def reply_to_query(inline_query: InlineQuery, bot) -> None:
    results = []
    switch = None
    user = inline_query.from_user
    user_id = user.id

    private_game = private_battles.game_for_user(user_id)
    gm.prune_stale_player_refs_for_user(user_id)
    players = gm.userid_players.get(user_id) or []

    n_loc = push_game_locales_for_user_chat(user, None)
    try:
        if private_game is not None and private_game.status in ("active", "pending_start"):
            _add_private_inline_results(results, private_game, user_id)

            suffixed = []
            for result in results:
                nid = f"{result.id}:{private_game.turn_token}:-1"
                suffixed.append(result.model_copy(update={"id": nid}))
            results = suffixed

        elif not players:
            add_no_game(results)

        else:
            player = gm.resolve_inline_player(user_id)
            if player is None:
                add_no_game(results)
            else:
                gm.userid_current[user_id] = player
                game = player.game
                if not gm.is_game_registered(game):
                    logger.debug(
                        "reply_to_query: user_id=%s unregistered game_id=%s",
                        user_id,
                        id(game),
                    )
                    add_no_game(results)
                else:
                    if not game.started:
                        if user_is_creator(user, game):
                            add_mode_classic(results)
                            add_mode_fast(results)
                            add_mode_wild(results)
                            add_mode_rainbow(results)
                            add_mode_sudden_death(results)
                            add_mode_no_mercy(results)
                            add_mode_text(results)
                            add_mode_team(results)
                        else:
                            add_not_started(results)

                    elif user_id == game.current_player.user.id:
                        if (
                            game.mode == "no_mercy"
                            and getattr(game, "mercy_extra_discard_pending", False)
                        ):
                            add_mercy_bonus_discard(results, game, player)
                        elif game.mode == "no_mercy" and getattr(
                            game, "mercy_pending_swap", False
                        ):
                            add_mercy_choose_opponent(
                                results,
                                game,
                                player,
                                prefix="nmswap_",
                                title_fmt=_("🔀 Swap with %s"),
                            )
                            add_other_cards(player, results, game)
                        elif game.mode == "no_mercy" and getattr(
                            game, "mercy_pending_roulette", None
                        ) == "target":
                            add_mercy_choose_opponent(
                                results,
                                game,
                                player,
                                prefix="nmroulette_",
                                title_fmt=_("🎰 Target %s"),
                            )
                            add_other_cards(player, results, game)
                        elif game.choosing_color or (
                            game.mode == "no_mercy"
                            and getattr(game, "mercy_pending_roulette", None) == "color"
                        ):
                            add_choose_color(results, game)
                            add_other_cards(player, results, game)
                        else:
                            if game.mode == "no_mercy":
                                add_no_mercy_turn_cards(player, results, game)
                            else:
                                if not player.drew:
                                    add_draw(player, results)
                                else:
                                    add_pass(results, game)

                                if (
                                    supports_bluff_challenge(game)
                                    and game.last_card.special in (c.DRAW_FOUR, c.DRAW_EIGHT)
                                    and game.draw_counter
                                    and getattr(game, "last_draw_special_challengeable", False)
                                ):
                                    add_call_bluff(results, game)

                                playable = player.playable_cards()
                                playable_ids = {str(card) for card in playable}
                                hand = sorted(player.cards, key=str)

                                for index, card in enumerate(hand):
                                    add_card(
                                        game,
                                        card,
                                        results,
                                        can_play=str(card) in playable_ids,
                                        hand_index=index,
                                    )

                                add_gameinfo(game, results)

                    elif user_id != game.current_player.user.id or not game.started:
                        hand = sorted(player.cards, key=str)
                        for index, card in enumerate(hand):
                            add_card(
                                game,
                                card,
                                results,
                                can_play=False,
                                hand_index=index,
                            )
                    else:
                        add_gameinfo(game, results)

                    suffixed = []
                    for result in results:
                        nid = _inline_result_id(result.id, player, game)
                        suffixed.append(result.model_copy(update={"id": nid}))
                    results = suffixed

                    if players and game and len(players) > 1:
                        switch = _("Current game: {game}").format(
                            game=game.chat.title or "",
                        )
    finally:
        pop_locale_stack_n(n_loc)

    await answer_inline_query(
        bot,
        inline_query.id,
        results,
        cache_time=0,
        switch_pm_text=switch,
        switch_pm_parameter="select",
    )


@router.chosen_inline_result()
async def process_result(chosen: ChosenInlineResult, bot) -> None:
    user, chat = user_chat_for_chosen_inline_result(chosen)
    n_loc = push_game_locales_for_user_chat(user, chat)
    try:
        raw_id = chosen.result_id
        try:
            result_id, anti_cheat, target_chat_id, inline_mode = _parse_inline_result_id(raw_id)
        except ValueError:
            logger.warning(
                "process_result: unparseable result_id=%r user_id=%s",
                raw_id,
                getattr(user, "id", None),
            )
            return

        # ------------------------------------------------------------------
        # Private battle inline flow
        # ------------------------------------------------------------------
        if result_id.startswith("pv|"):
            game = private_battles.game_for_user(user.id)
            if not game:
                logger.info(
                    "Chosen private inline ignored: no active private game user_id=%s",
                    user.id,
                )
                return

            if game.status not in ("active", "pending_start"):
                return

            if int(anti_cheat) != int(game.turn_token):
                logger.info(
                    "Chosen private inline rejected stale token user_id=%s expected=%s got=%s",
                    user.id,
                    game.turn_token,
                    anti_cheat,
                )
                return

            parts = result_id.split("|")
            action = parts[1] if len(parts) > 1 else ""

            if action in {"wait", "wait_turn", "draw_text", "blocked"}:
                return

            ok = False
            err = ""

            if action == "draw":
                ok, err = await private_battles.draw_card(
                    game.game_id,
                    user.id,
                    int(anti_cheat),
                )
            elif action == "pass":
                ok, err = await private_battles.pass_turn(
                    game.game_id,
                    user.id,
                    int(anti_cheat),
                )
            elif action == "play" and len(parts) >= 3:
                ok, err = await private_battles.play_card(
                    game.game_id,
                    user.id,
                    int(anti_cheat),
                    parts[2],
                )
            elif action == "color" and len(parts) >= 3:
                ok, err = await private_battles.choose_color(
                    game.game_id,
                    user.id,
                    int(anti_cheat),
                    parts[2],
                )
            elif action == "challenge":
                ok, err = await private_battles.challenge_draw_four(
                    game.game_id,
                    user.id,
                    int(anti_cheat),
                )
            else:
                return

            if not ok:
                logger.info(
                    "Chosen private inline rejected user_id=%s action=%s err=%s",
                    user.id,
                    action,
                    err,
                )
                schedule_audit_telegram(
                    "private_inline_action_rejected",
                    action="private_inline_reject",
                    actor=format_user(user),
                    game_id=game.game_id,
                    inline_action=action,
                    reason=err,
                )
                return

            schedule_audit_telegram(
                "private_inline_action_applied",
                action="private_inline_apply",
                actor=format_user(user),
                game_id=game.game_id,
                inline_action=action,
                turn_user_id=game.current_turn_user_id,
                turn_token=game.turn_token,
            )
            await sync_private_boards(bot, game, actor_id=user.id)
            return

        # ------------------------------------------------------------------
        # Normal public / group UNO flow
        # ------------------------------------------------------------------
        if target_chat_id is not None:
            player = gm.player_for_user_in_chat_id(user, target_chat_id)
            if not player:
                logger.info(
                    "Chosen inline ignored: no player for user_id=%s chat_id=%s",
                    user.id,
                    target_chat_id,
                )
                return
            gm.userid_current[user.id] = player
        else:
            player = None
            try:
                player = gm.userid_current[user.id]
            except KeyError:
                pass

            if player is None:
                plist = gm.userid_players.get(user.id) or []
                if len(plist) == 1:
                    player = plist[0]
                    gm.userid_current[user.id] = player
                    logger.warning(
                        "process_result: legacy inline id (no chat suffix); "
                        "single-game fallback user_id=%s raw_id=%r",
                        user.id,
                        raw_id,
                    )

            if player is None:
                logger.info(
                    "Chosen inline ignored: no userid_current / player list "
                    "user_id=%s raw_id=%r",
                    user.id,
                    raw_id,
                )
                return

        game = player.game
        chat = game.chat

        if inline_mode and inline_mode != getattr(game, "mode", None):
            logger.info(
                "Chosen inline rejected mode mismatch: user_id=%s expected_mode=%s game_mode=%s stem=%s",
                user.id,
                inline_mode,
                getattr(game, "mode", None),
                result_id,
            )
            return

        gm.note_last_inline_chat(user.id, chat.id)

        if not gm.is_game_registered(game):
            logger.info(
                "Chosen inline ignored (stale): user_id=%s player_id=%s game_id=%s "
                "chat_id=%s not in registered games",
                user.id,
                id(player),
                id(game),
                getattr(chat, "id", None),
            )
            return

        logger.info(
            "Chosen inline raw_id=%s stem=%s user_id=%s player_id=%s "
            "current_player_id=%s game_id=%s chat_id=%s",
            raw_id,
            result_id,
            user.id,
            id(player),
            id(game.current_player) if game.current_player else None,
            id(game),
            chat.id,
        )

        if result_id in ("hand", "gameinfo", "nogame"):
            return

        if result_id.startswith("bh") or result_id.startswith("blocked_"):
            return

        if result_id.startswith("mode_"):
            mode = result_id[5:]
            if not await user_is_creator_or_admin_aiogram(user, game, bot, chat):
                logger.info(
                    "Chosen inline mode change rejected (not owner/admin): user_id=%s mode=%s chat_id=%s",
                    user.id,
                    mode,
                    chat.id,
                )
                return
            if mode == "team":
                await send_message(
                    bot,
                    chat.id,
                    text=__("Team mode is available with /teamnew (2v2/3v3, manual/random)."),
                )
                return

            game.set_mode(mode)
            if mode == "no_mercy":
                from no_mercy import configure_new_lobby

                configure_new_lobby(game)
            logger.info("Gamemode changed to {mode}".format(mode=mode))
            await send_message(
                bot,
                chat.id,
                text=__("Gamemode changed to {mode}".format(mode=mode)),
            )
            return

        if len(result_id) == 36:
            return

        if game.mode == "no_mercy" and game.started:
            from no_mercy.state import is_eliminated_uid

            if is_eliminated_uid(game, user.id):
                return

        if game.started and user.id != game.current_player.user.id:
            logger.info(
                "Chosen inline ignored (not current turn): user_id=%s current_uid=%s "
                "player_obj_id=%s current_player_obj_id=%s chat_id=%s",
                user.id,
                game.current_player.user.id,
                id(player),
                id(game.current_player),
                chat.id,
            )
            return

        if game.started:
            player = game.current_player
            gm.userid_current[user.id] = player

        last_anti_cheat = player.anti_cheat
        player.anti_cheat += 1

        if int(anti_cheat) != last_anti_cheat:
            logger.info(
                "Chosen inline rejected anti_cheat: user=%s expected=%s got=%s stem=%s",
                user.id,
                last_anti_cheat,
                anti_cheat,
                result_id,
            )
            await send_message(
                bot,
                chat.id,
                text=__("Cheat attempt by {name}", multi=game.translate).format(
                    name=display_name_html(player.user)
                ),
                parse_mode=ParseMode.HTML,
            )
            return

        cancel_fast_countdown(game)

        if result_id == "call_bluff":
            from modes.capabilities import supports_bluff_challenge

            if not supports_bluff_challenge(game):
                return
            if (
                game.last_card.special not in (c.DRAW_FOUR, c.DRAW_EIGHT)
                or not game.draw_counter
                or not getattr(game, "last_draw_special_challengeable", False)
            ):
                return
            await reset_waiting_time(bot, player)
            await do_call_bluff(bot, player)
        elif result_id == "draw":
            if player.drew and game.draw_counter == 0:
                logger.info(
                    "Chosen inline draw ignored (already drew): user_id=%s chat_id=%s",
                    user.id,
                    chat.id,
                )
                return
            await reset_waiting_time(bot, player)
            await do_draw(bot, player)
        elif result_id == "pass":
            if game.mode == "no_mercy":
                return
            if not player.drew:
                logger.info(
                    "Chosen inline pass ignored (draw required): user_id=%s chat_id=%s",
                    user.id,
                    chat.id,
                )
                return
            game.turn()
        elif result_id in c.mode_colors(game.mode):
            if not game.choose_color(result_id):
                logger.info(
                    "Chosen inline color ignored (no pending color choice): user_id=%s chat_id=%s",
                    user.id,
                    chat.id,
                )
                return
            if game.mode == "no_mercy":
                from no_mercy.actions_hook import after_color_choice

                await after_color_choice(bot, game.current_player)
                if not game_is_running(game):
                    return
            if game.mode == "no_mercy" and getattr(
                game, "mercy_pending_roulette", None
            ) == "target":
                pass
        elif game.mode == "no_mercy" and result_id.startswith("nmbonus"):
            from no_mercy.constants import BONUS_DISCARD_INFO_ID, BONUS_DISCARD_SKIP_ID
            from no_mercy.actions_hook import (
                handle_bonus_discard_index,
                handle_bonus_discard_skip,
            )
            from no_mercy.extra_discard import card_index_from_result

            if result_id in (BONUS_DISCARD_INFO_ID, BONUS_DISCARD_SKIP_ID):
                if result_id == BONUS_DISCARD_SKIP_ID:
                    await handle_bonus_discard_skip(bot, player)
                return
            idx = card_index_from_result(result_id)
            if idx is not None:
                await handle_bonus_discard_index(bot, player, idx)
        elif game.mode == "no_mercy" and result_id.startswith("nmswap_"):
            from no_mercy.actions_hook import handle_swap_target

            await reset_waiting_time(bot, player)
            await handle_swap_target(bot, player, int(result_id[7:]))
        elif game.mode == "no_mercy" and result_id.startswith("nmroulette_"):
            from no_mercy.actions_hook import handle_roulette_target

            await reset_waiting_time(bot, player)
            await handle_roulette_target(bot, player, int(result_id[11:]))
        else:
            if game.mode == "no_mercy":
                from no_mercy.game_state import blocks_normal_play

                if blocks_normal_play(game):
                    return
            await reset_waiting_time(bot, player)
            await do_play_card(bot, player, result_id)

        if game_is_running(game):
            nextplayer_message = __(
                "ɴᴇxᴛ ᴘʟᴀʏᴇʀ: {name}",
                multi=game.translate,
            ).format(name=display_name_html(game.current_player.user))

            choice = [
                [btn_switch_current_chat(_("Make your choice!"), "", "success")]
            ]
            from no_mercy.ui.prompt import send_turn_prompt_compat

            await send_turn_prompt_compat(
                bot,
                game,
                nextplayer_message,
                markup(choice),
            )
            await start_player_countdown(bot, game)
        else:
            await delete_game_turn_prompt_safe(bot, game)
    finally:
        pop_locale_stack_n(n_loc)