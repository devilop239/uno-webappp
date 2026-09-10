# -*- coding: utf-8 -*-
"""Load and format player_stats for /mystats and menus."""

from html import escape
import logging
from typing import Any, Dict, List, Optional, Tuple

from config import (
    ABANDON_PENALTY,
    LARGE_MATCH_BONUS,
    LARGE_MATCH_MIN_PLAYERS,
    MIN_VALID_PLAYERS_FOR_POINTS,
    MIN_VALID_TURNS_FOR_POINTS,
    PARTICIPATION_POINTS,
    SECOND_PLACE_POINTS,
    STREAK_BONUS_3,
    STREAK_BONUS_5,
    THIRD_PLACE_POINTS,
    WIN_POINTS,
)
from db.mongo_client import fetch_player_stats_document, get_database
from internationalization import _
from services import leaderboard_service
from ui.text_style import custom_emoji_heading_html, menu_heading_bold, smallcaps

logger = logging.getLogger(__name__)

_POINTS_EMOJI_HEADER = "6314237464315696206"
_POINTS_EMOJI_BALANCES = "6073456529640525999"
_POINTS_EMOJI_EARN = "5327928143531486985"
_POINTS_EMOJI_COUNTED = "6179375809048875316"


def fetch_player_stats_row(user_id: int) -> Optional[Dict[str, Any]]:
    db = get_database()
    if db is None:
        return None
    return fetch_player_stats_document(db, user_id)


def fetch_recent_matches(user_id: int, limit: int = 5) -> list:
    db = get_database()
    if db is None:
        return []
    try:
        uid = int(user_id)
        cur = (
            db.matches.find({"player_ids": uid})
            .sort("ended_at", -1)
            .limit(limit)
        )
        return list(cur)
    except Exception:
        logger.exception("fetch_recent_matches failed")
        return []


def format_mystats_html(user_id: int) -> str:
    db = get_database()
    if db is None:
        return _("Add <code>MONGO_URI</code> to your environment to enable persistent stats.")
    row = fetch_player_stats_row(user_id)
    if not row:
        row = {}
    gp = int(row.get("games_played") or 0)
    gw = int(row.get("games_won") or 0)
    gl = int(row.get("games_lost") or 0)
    wr = round(100.0 * gw / gp) if gp else 0
    r_all = leaderboard_service.rank_for_user(user_id, "total")
    r_w = leaderboard_service.rank_for_user(user_id, "weekly")
    r_s = leaderboard_service.rank_for_user(user_id, "season")
    rank_line = ""
    if r_all or r_w or r_s:
        parts = []
        if r_all:
            parts.append("All-time #%d" % r_all)
        if r_w:
            parts.append("Week #%d" % r_w)
        if r_s:
            parts.append("Season #%d" % r_s)
        rank_line = "\n" + " · ".join(parts)
    return (
        "<b>%s</b>\n"
        "Total <code>%d</code> · Season <code>%d</code> · Week <code>%d</code> · Month <code>%d</code>\n"
        "\n<b>%s</b>\n"
        "Played <code>%d</code> · Wins <code>%d</code> · Losses <code>%d</code>\n"
        "Win rate <code>%d%%</code>\n"
        "Streak <code>%d</code> (best <code>%d</code>)%s"
        % (
            smallcaps(_("Points")),
            int(row.get("total_points") or 0),
            int(row.get("season_points") or 0),
            int(row.get("weekly_points") or 0),
            int(row.get("monthly_points") or 0),
            smallcaps(_("Performance")),
            gp,
            gw,
            gl,
            wr,
            int(row.get("current_win_streak") or 0),
            int(row.get("best_win_streak") or 0),
            rank_line,
        )
    )


def _ledger_reason_totals(user_id: int) -> Dict[str, int]:
    db = get_database()
    if db is None:
        return {}
    try:
        uid = int(user_id)
        out: Dict[str, int] = {}
        for doc in db.point_ledger.aggregate(
            [
                {"$match": {"user_id": uid}},
                {"$group": {"_id": "$reason", "t": {"$sum": "$delta"}}},
            ]
        ):
            key = doc.get("_id") or "?"
            out[str(key)] = int(doc.get("t") or 0)
        return out
    except Exception:
        logger.exception("_ledger_reason_totals failed user_id=%s", user_id)
        return {}


def _reason_label(reason: str) -> str:
    r = reason or "?"
    if r == "win":
        return _("Match win")
    if r == "participation":
        return _("Participation")
    if r == "second_place":
        return _("2nd place")
    if r == "third_place":
        return _("3rd place")
    if r == "large_match":
        return _("Large match bonus")
    if r == "streak_bonus":
        return _("Win streak bonus")
    if r == "abandon_penalty":
        return _("Abandon penalty")
    if r == "admin_gift":
        return _("Admin gift")
    return r.replace("_", " ")


def _earn_rules_bullet_lines() -> List[str]:
    return [
        "• %s: <code>+%d</code>" % (smallcaps(_("Win")), WIN_POINTS),
        "• %s: <code>+%d</code>" % (smallcaps(_("Finished match")), PARTICIPATION_POINTS),
        "• %s: <code>+%d</code>" % (smallcaps(_("2nd place")), SECOND_PLACE_POINTS),
        "• %s: <code>+%d</code>" % (smallcaps(_("3rd place")), THIRD_PLACE_POINTS),
        "• %s: <code>+%d</code>" % (smallcaps(_("Win streak 3–4")), STREAK_BONUS_3),
        "• %s: <code>+%d</code>" % (smallcaps(_("Win streak 5+")), STREAK_BONUS_5),
        "• %s: <code>+%d</code>"
        % (
            smallcaps(
                _("Large match (%(n)d+)")
                % {"n": LARGE_MATCH_MIN_PLAYERS}
            ),
            LARGE_MATCH_BONUS,
        ),
        "• %s: <code>-%d</code>" % (smallcaps(_("Abandon / timeout")), ABANDON_PENALTY),
    ]


def _counted_match_section_lines() -> List[str]:
    return [
        "",
        custom_emoji_heading_html(
            _POINTS_EMOJI_COUNTED,
            "📌",
            _("Counted match"),
        ),
        "• %s"
        % smallcaps(
            _("%(p)d+ players") % {"p": MIN_VALID_PLAYERS_FOR_POINTS}
        ),
        "• %s"
        % smallcaps(
            _("%(t)d+ turns") % {"t": MIN_VALID_TURNS_FOR_POINTS}
        ),
    ]


def format_points_detail_html(user_id: int) -> str:
    """Full /points view: balances, ledger by reason, scoring rules."""
    db = get_database()
    if db is None:
        return (
            custom_emoji_heading_html(_POINTS_EMOJI_HEADER, "⭐", _("Points"))
            + "\n\n"
            + _(
                "Add <code>MONGO_URI</code> to your environment to enable persistent stats."
            )
        )

    row = fetch_player_stats_row(user_id) or {}
    tp = int(row.get("total_points") or 0)
    sp = int(row.get("season_points") or 0)
    wp = int(row.get("weekly_points") or 0)
    mp = int(row.get("monthly_points") or 0)

    r_all = leaderboard_service.rank_for_user(user_id, "total")
    r_w = leaderboard_service.rank_for_user(user_id, "weekly")
    r_m = leaderboard_service.rank_for_user(user_id, "monthly")
    r_s = leaderboard_service.rank_for_user(user_id, "season")
    rank_bits = []
    if r_all:
        rank_bits.append("<code>#%d</code> %s" % (r_all, smallcaps(_("all-time"))))
    if r_w:
        rank_bits.append("<code>#%d</code> %s" % (r_w, smallcaps(_("week"))))
    if r_m:
        rank_bits.append("<code>#%d</code> %s" % (r_m, smallcaps(_("month"))))
    if r_s:
        rank_bits.append("<code>#%d</code> %s" % (r_s, smallcaps(_("season"))))
    rank_line = (
        ("• %s: %s" % (smallcaps(_("Rank")), " · ".join(rank_bits)))
        if rank_bits
        else ""
    )

    lines: List[str] = [
        custom_emoji_heading_html(_POINTS_EMOJI_HEADER, "⭐", _("Points")),
        "",
        custom_emoji_heading_html(_POINTS_EMOJI_BALANCES, "✨", _("Your balances")),
        "• %s: <code>%d</code>" % (smallcaps(_("All-time")), tp),
        "• %s: <code>%d</code>" % (smallcaps(_("This season")), sp),
        "• %s: <code>%d</code>" % (smallcaps(_("This week")), wp),
        "• %s: <code>%d</code>" % (smallcaps(_("This month")), mp),
    ]
    if rank_line:
        lines.append(rank_line)

    ledger = _ledger_reason_totals(user_id)
    if ledger:
        lines.append("")
        lines.append(
            menu_heading_bold(_("Your points by source (all-time ledger)"))
        )
        pairs: List[Tuple[str, int]] = sorted(ledger.items(), key=lambda x: -abs(x[1]))
        for reason, total in pairs[:16]:
            lines.append(
                "• %s: <code>%+d</code>" % (_reason_label(reason), total)
            )

    lines.append("")
    lines.append(
        custom_emoji_heading_html(_POINTS_EMOJI_EARN, "💎", _("Earn rules"))
    )
    lines.extend(_earn_rules_bullet_lines())
    lines.extend(_counted_match_section_lines())

    return "\n".join(lines)


def format_stats_menu_lines(user_id: int) -> str:
    """HTML lines for the private menu statistics view."""
    db = get_database()
    if db is None:
        return _("Stats sync is off until MongoDB is configured (set MONGO_URI).")
    row = fetch_player_stats_row(user_id)
    if not row:
        row = {}
    gp = int(row.get("games_played") or 0)
    gw = int(row.get("games_won") or 0)
    m = round(100.0 * gw / gp) if gp else 0
    return (
        "Points · total <code>%d</code>\n"
        "Games · <code>%d</code> played, <code>%d</code> wins (<code>%d%%</code>)\n"
        "Cards played · <code>%d</code>\n"
        "Streak · <code>%d</code> (best <code>%d</code>)"
        % (
            int(row.get("total_points") or 0),
            gp,
            gw,
            m,
            int(row.get("cards_played") or 0),
            int(row.get("current_win_streak") or 0),
            int(row.get("best_win_streak") or 0),
        )
    )


def format_match_history_html(user_id: int) -> str:
    rows = fetch_recent_matches(user_id, limit=8)
    if not rows:
        return "<i>No recent matches recorded.</i>"
    db = get_database()
    
    # Pre-fetch all unique chat titles in a single query to avoid N+1 problem
    chat_ids = set()
    for r in rows:
        if not r.get("chat_title"):
            try:
                cid = int(r.get("chat_id"))
                if cid:
                    chat_ids.add(cid)
            except (TypeError, ValueError):
                pass
    
    chat_title_map: Dict[int, str] = {}
    if chat_ids and db is not None:
        try:
            pipeline = [
                {"$match": {"chat_id": {"$in": list(chat_ids)}, "chat_title": {"$type": "string", "$ne": ""}}},
                {"$sort": {"ended_at": -1}},
                {"$group": {"_id": "$chat_id", "chat_title": {"$first": "$chat_title"}}}
            ]
            for doc in db.matches.aggregate(pipeline):
                try:
                    cid = int(doc.get("_id"))
                    title = str(doc.get("chat_title") or "").strip()
                    if cid and title:
                        chat_title_map[cid] = title
                except (TypeError, ValueError):
                    pass
        except Exception:
            logger.exception("batch chat_title lookup failed")

    def _place_label(place: int) -> str:
        place = int(place or 0)
        if place == 1:
            return _("1st place")
        if place == 2:
            return _("2nd place")
        if place == 3:
            return _("3rd place")
        return _("Place %(n)d") % {"n": place}

    def _result_label(row: Dict[str, Any], uid: int) -> str:
        status = str(row.get("status") or "").lower()
        placements = row.get("placements") or []
        if isinstance(placements, list):
            for p in placements:
                if int(p.get("user_id") or 0) == uid:
                    return _place_label(int(p.get("place") or 0))
        if bool(row.get("team_mode")):
            winning_team_id = str(row.get("winning_team_id") or "").upper()
            if winning_team_id in ("A", "B"):
                members = row.get("team_members") or {}
                winners = set(int(x) for x in (members.get(winning_team_id) or []))
                return _("1st place") if uid in winners else _("2nd place")
        if status == "cancelled":
            return _("Cancelled")
        if status == "invalid":
            return _("Invalid")
        if status == "completed":
            return _("Lost")
        return _("Unknown")

    lines = []
    for r in rows:
        chat_title = str(r.get("chat_title") or "").strip()
        if not chat_title:
            try:
                cid = int(r.get("chat_id"))
                chat_title = chat_title_map.get(cid, "") or _("Unknown Group")
            except (TypeError, ValueError):
                chat_title = _("Unknown Group")
        result = _result_label(r, int(user_id))
        pts = r.get("points_awarded") or {}
        my_pts = 0
        if isinstance(pts, dict):
            my_pts = int(pts.get(str(user_id), 0))
        mode = str(r.get("game_mode") or "").strip() or "uno"
        lines.append(
            "• <b>%s</b>\n%s: <code>%+d</code> · %s: <code>%s</code> · %s: <code>%s</code>"
            % (
                escape(chat_title),
                smallcaps(_("Points")),
                my_pts,
                smallcaps(_("Result")),
                escape(result),
                smallcaps(_("Mode")),
                escape(mode),
            )
        )
    return "\n".join(lines)
