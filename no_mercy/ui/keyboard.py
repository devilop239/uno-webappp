"""Build inline keyboards for NO MERCY turn UI."""
from __future__ import annotations

import deck.card as c

from ui.inline_buttons import btn_callback, markup
from no_mercy.extra_discard import is_pending as bonus_pending, sorted_hand
from no_mercy.playability import playable_cards
from no_mercy.ui import config as ui_cfg
from no_mercy.ui.renderer import card_label
from no_mercy.ui.tokens import build_callback


def _page_cards(game, player, page: int) -> tuple[list, int]:
    if bonus_pending(game):
        hand = sorted_hand(player)
        per = ui_cfg.CARDS_PER_PAGE
        total_pages = max(1, (len(hand) + per - 1) // per)
        page = max(0, min(page, total_pages - 1))
        chunk = hand[page * per : (page + 1) * per]
        return chunk, total_pages

    cards = sorted(playable_cards(player), key=str)
    per = ui_cfg.CARDS_PER_PAGE
    total_pages = max(1, (len(cards) + per - 1) // per)
    page = max(0, min(page, total_pages - 1))
    chunk = cards[page * per : (page + 1) * per]
    return chunk, total_pages


def build_keyboard(game, player, *, page: int = 0) -> dict:
    rows = []

    if bonus_pending(game):
        chunk, total_pages = _page_cards(game, player, page)
        card_rows = []
        row = []
        for i, card in enumerate(chunk):
            global_index = page * ui_cfg.CARDS_PER_PAGE + i
            row.append(
                btn_callback(
                    "🗑️ %s" % card_label(card)[:28],
                    build_callback(ui_cfg.ACT_BONUS, game, str(global_index)),
                    "danger",
                )
            )
            if len(row) >= ui_cfg.CARDS_PER_ROW:
                card_rows.append(row)
                row = []
        if row:
            card_rows.append(row)
        rows.extend(card_rows)
        if total_pages > 1:
            nav = []
            if page > 0:
                nav.append(
                    btn_callback(
                        "◀️ Prev",
                        build_callback(ui_cfg.ACT_PAGE, game, str(page - 1)),
                        "default",
                    )
                )
            if page < total_pages - 1:
                nav.append(
                    btn_callback(
                        "▶️ Next",
                        build_callback(ui_cfg.ACT_PAGE, game, str(page + 1)),
                        "default",
                    )
                )
            rows.append(nav)
        rows.append(
            [
                btn_callback(
                    "✓ Skip bonus",
                    build_callback(ui_cfg.ACT_BONUS_SKIP, game),
                    "success",
                ),
            ]
        )
        rows.append(_info_row(game))
        return markup(rows)

    pending_roulette = getattr(game, "mercy_pending_roulette", None)
    if pending_roulette == "color":
        rows.append(
            [
                btn_callback(
                    "❤️",
                    build_callback(ui_cfg.ACT_COLOR, game, "r"),
                    "danger",
                ),
                btn_callback(
                    "💙",
                    build_callback(ui_cfg.ACT_COLOR, game, "b"),
                    "primary",
                ),
                btn_callback(
                    "💚",
                    build_callback(ui_cfg.ACT_COLOR, game, "g"),
                    "success",
                ),
                btn_callback(
                    "💛",
                    build_callback(ui_cfg.ACT_COLOR, game, "y"),
                    "success",
                ),
            ]
        )
        rows.append(_info_row(game))
        return markup(rows)

    if pending_roulette == "target":
        rows.extend(_opponent_rows(game, player, ui_cfg.ACT_ROULETTE))
        rows.append(_info_row(game))
        return markup(rows)

    if getattr(game, "mercy_pending_swap", False):
        rows.extend(_opponent_rows(game, player, ui_cfg.ACT_SWAP))
        rows.append(_info_row(game))
        return markup(rows)

    if game.choosing_color:
        rows.append(
            [
                btn_callback("❤️", build_callback(ui_cfg.ACT_COLOR, game, "r"), "danger"),
                btn_callback("💙", build_callback(ui_cfg.ACT_COLOR, game, "b"), "primary"),
                btn_callback("💚", build_callback(ui_cfg.ACT_COLOR, game, "g"), "success"),
                btn_callback("💛", build_callback(ui_cfg.ACT_COLOR, game, "y"), "success"),
            ]
        )
        rows.append(_info_row(game))
        return markup(rows)

    chunk, total_pages = _page_cards(game, player, page)
    card_rows = []
    row = []
    base_index = page * ui_cfg.CARDS_PER_PAGE
    playable = playable_cards(player)
    for i, card in enumerate(chunk):
        row.append(
            btn_callback(
                card_label(card)[:32],
                build_callback(ui_cfg.ACT_PLAY, game, str(base_index + i)),
                "primary",
            )
        )
        if len(row) >= ui_cfg.CARDS_PER_ROW:
            card_rows.append(row)
            row = []
    if row:
        card_rows.append(row)
    rows.extend(card_rows)

    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append(
                btn_callback(
                    "◀️ Prev",
                    build_callback(ui_cfg.ACT_PAGE, game, str(page - 1)),
                    "default",
                )
            )
        if page < total_pages - 1:
            nav.append(
                btn_callback(
                    "▶️ Next",
                    build_callback(ui_cfg.ACT_PAGE, game, str(page + 1)),
                    "default",
                )
            )
        if nav:
            rows.append(nav)

    controls = [
        btn_callback("👁 Hand", build_callback(ui_cfg.ACT_HAND, game), "default"),
        btn_callback("ℹ️ Refresh", build_callback(ui_cfg.ACT_INFO, game), "success"),
    ]
    if game.draw_counter:
        controls.insert(
            0,
            btn_callback(
                "🃏 Draw stack (%d)" % game.draw_counter,
                build_callback(ui_cfg.ACT_DRAW, game),
                "danger",
            ),
        )
    elif not player.drew:
        controls.insert(
            0,
            btn_callback("🃏 Draw", build_callback(ui_cfg.ACT_DRAW, game), "primary"),
        )
    else:
        controls.append(
            btn_callback("⏭ Pass", build_callback(ui_cfg.ACT_PASS, game), "default")
        )
    rows.append(controls)
    return markup(rows)


def _info_row(game) -> list:
    return [
        btn_callback("👁 Hand", build_callback(ui_cfg.ACT_HAND, game), "default"),
        btn_callback("ℹ️ Refresh", build_callback(ui_cfg.ACT_INFO, game), "success"),
    ]


def _opponent_rows(game, current, action: str) -> list:
    rows = []
    row = []
    idx = 0
    for p in game.players:
        if p is current:
            continue
        from utils import display_name_label

        name = display_name_label(p.user)
        if len(name) > 18:
            name = name[:17] + "…"
        row.append(
            btn_callback(
                name,
                build_callback(action, game, str(idx)),
                "primary",
            )
        )
        idx += 1
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return rows


def playable_card_at_index(player, index: int):
    """Map keyboard index to playable card (sorted)."""
    cards = sorted(playable_cards(player), key=str)
    if 0 <= index < len(cards):
        return cards[index]
    return None


def opponent_at_index(game, current, index: int):
    others = [p for p in game.players if p is not current]
    if 0 <= index < len(others):
        return others[index]
    return None
