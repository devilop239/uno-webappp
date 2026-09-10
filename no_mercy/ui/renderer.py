"""NO MERCY status text renderer (HTML)."""
from __future__ import annotations

import html

import deck.card as c

from no_mercy import state
from no_mercy.constants import (
    DRAW2,
    ELIMINATION_HAND_SIZE,
    W_DRAW4,
    W_DRAW4_REVERSE,
    W_DRAW6,
    W_DRAW10,
    W_ROULETTE,
    W_SKIP_ALL,
    W_WILD,
)
from no_mercy.text_style import sc, sc_bold
from utils import display_name_html


_COLOR_EMOJI = {"r": "❤️", "b": "💙", "g": "💚", "y": "💛"}
_COLOR_NAME = {"r": "Red", "b": "Blue", "g": "Green", "y": "Yellow"}

_WILD_LABELS = {
    W_WILD: "Wild",
    W_DRAW4: "+4",
    W_DRAW6: "+6",
    W_DRAW10: "+10",
    W_DRAW4_REVERSE: "+4 Reverse",
    W_SKIP_ALL: "Skip All",
    W_ROULETTE: "Roulette",
}


def _esc(text: str) -> str:
    return html.escape(str(text), quote=False)


def card_label(card) -> str:
    if card.special:
        label = _WILD_LABELS.get(card.special)
        if label:
            raw = label if label == "Wild" else "Wild %s" % label
        else:
            name = card.special.replace("w_", "").replace("_", " ").title()
            raw = "Wild %s" % name
        return sc(raw)
    icon = _COLOR_EMOJI.get(card.color, "")
    val = card.value
    if val == DRAW2:
        val = "+2"
    elif val == "discard_all":
        val = "Discard All"
    return sc(("%s %s" % (icon, val)).strip())


def top_card_line(game) -> str:
    card = game.last_card
    if not card:
        return "—"
    label = card_label(card)
    if card.color:
        label = "%s %s" % (_COLOR_NAME.get(card.color, card.color), label.split(" ", 1)[-1])
    return label


def direction_arrow(game) -> str:
    return "↩️" if getattr(game, "reversed", False) else "↪️"


def player_line(game, player) -> str:
    uid = int(player.user.id)
    name = display_name_html(player.user)
    n = len(player.cards)
    tags = []
    if uid in (getattr(game, "eliminated_players", []) or []):
        tags.append("💀")
    elif player is game.current_player:
        tags.append("▶️")
    if n == 1:
        tags.append("🃏")
    elif n >= max(1, ELIMINATION_HAND_SIZE - 5):
        tags.append("⚠️")
    suffix = (" " + " ".join(tags)) if tags else ""
    return "%s → <b>%d</b> %s%s" % (name, n, sc("cards"), suffix)


def render_status(game, *, header: str | None = None) -> str:
    cur = game.current_player
    lines = [
        sc_bold("🔥 NO MERCY MODE"),
        "",
    ]
    if header:
        lines.append(header)
        lines.append("")

    lines.extend(
        [
            "%s %s" % (sc_bold("Current:"), display_name_html(cur.user)),
            "%s %s" % (sc_bold("Top card:"), _esc(top_card_line(game))),
            "%s %s" % (sc_bold("Direction:"), direction_arrow(game)),
        ]
    )

    stack = int(game.draw_counter or 0)
    if stack:
        alert = " 💀" if stack >= 20 else (" ⚠️" if stack >= 10 else "")
        lines.append("%s +%d%s" % (sc_bold("Stack:"), stack, alert))
    else:
        lines.append("%s —" % sc_bold("Stack:"))

    deck = getattr(game, "deck", None)
    remaining = len(getattr(deck, "cards", []) or []) if deck else 0
    lines.append("%s %d %s" % (sc_bold("Deck:"), remaining, sc("cards")))

    pending = getattr(game, "mercy_pending_roulette", None)
    if pending == "color":
        lines.append("🎰 %s" % sc_bold("Roulette — choose color"))
    elif pending == "target":
        lines.append("🎰 %s" % sc_bold("Roulette — choose target"))
    elif getattr(game, "mercy_pending_swap", False):
        lines.append("🔀 %s" % sc_bold("Swap — choose player"))

    lines.append("")
    lines.append(sc_bold("Players:"))
    for p in game.players:
        lines.append(player_line(game, p))

    eliminated = getattr(game, "eliminated_players", []) or []
    if eliminated:
        lines.append("")
        lines.append("<i>☠️ %s %s</i>" % (sc("Eliminated IDs:"), ", ".join(str(x) for x in eliminated)))

    return "\n".join(lines)


def render_hand_private(player) -> str:
    cards = sorted(player.cards, key=str)
    if not cards:
        return sc("Your hand is empty.")
    labels = [card_label(x) for x in cards]
    return "%s (%d):\n%s" % (sc_bold("Your hand"), len(cards), ", ".join(_esc(x) for x in labels))


def render_winner_screen(game, winner_user) -> str:
    stats = __import__("no_mercy.stats", fromlist=["snapshot"]).snapshot(game)
    lines = [
        sc_bold("🏆 NO MERCY WINNER!"),
        "",
        "%s %s" % (sc_bold("Winner:"), display_name_html(winner_user)),
        "",
        sc_bold("Survivors in ring:"),
    ]
    for p in game.players:
        lines.append("• %s (%d %s)" % (display_name_html(p.user), len(p.cards), sc("cards")))

    eliminated = getattr(game, "eliminated_players", []) or []
    if eliminated:
        lines.append("")
        lines.append("%s %d %s" % (sc_bold("Eliminated:"), len(eliminated), sc("players")))

    lines.extend(
        [
            "",
            sc_bold("Match stats"),
            "%s <b>%d</b>" % (sc("Turns:"), stats["turns"]),
            "%s <b>+%d</b>" % (sc("Biggest stack:"), stats["max_stack"]),
            "%s <b>%d</b>" % (sc("Roulettes:"), stats["roulette_count"]),
        ]
    )
    return "\n".join(lines)


def render_roulette_sequence(
    actor_html: str,
    target_html: str,
    color: str,
    draws: list[tuple[str, bool]],
) -> str:
    """
    HTML roulette reveal. actor_html / target_html from display_name_html (linked names).
    """
    color_name = sc(_COLOR_NAME.get(color, color))
    lines = [
        "🎰 %s" % sc_bold("ROULETTE ACTIVATED!"),
        "%s %s %s!" % (actor_html, sc_bold("TARGETED"), target_html),
        sc("Drawing until %s appears…" % color_name),
        "",
    ]
    for label, hit in draws:
        mark = "✅" if hit else "❌"
        lines.append("%s %s" % (_esc(label), mark))
    return "\n".join(lines)
