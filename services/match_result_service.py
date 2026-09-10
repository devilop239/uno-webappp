# -*- coding: utf-8 -*-
"""Post-match score announcement with leaderboard shortcut."""

import html
from typing import Any, Dict, List, Optional

from db.mongo_client import get_database
from ui.inline_buttons import btn_callback, markup
from tg.helpers import send_message
from ui.text_style import menu_title_bar, smallcaps


def _safe_uid(value: Any) -> Optional[int]:
    try:
        uid = int(value)
    except (TypeError, ValueError):
        return None
    if uid <= 0:
        return None
    return uid


def _name_link(uid: int, label: str) -> str:
    txt = (label or "").strip() or "Player"
    return '<a href="tg://user?id=%d">%s</a>' % (uid, html.escape(txt))


def capture_match_context(game, fallback_user=None) -> Dict[str, Any]:
    """
    Capture stable player identity data before gm.end_game clears runtime state.
    """
    names: Dict[int, str] = {}
    for p in list(getattr(game, "players", []) or []):
        u = getattr(p, "user", None)
        uid = _safe_uid(getattr(u, "id", None))
        if uid is None:
            continue
        label = getattr(u, "first_name", None) or getattr(u, "username", None) or "Player"
        names[uid] = str(label)

    if fallback_user is not None:
        fuid = _safe_uid(getattr(fallback_user, "id", None))
        if fuid is not None and fuid not in names:
            flabel = (
                getattr(fallback_user, "first_name", None)
                or getattr(fallback_user, "username", None)
                or "Player"
            )
            names[fuid] = str(flabel)

    finish_order = []
    for uid in list(getattr(game, "finish_order", []) or []):
        suid = _safe_uid(uid)
        if suid is not None:
            finish_order.append(suid)

    participant_ids = []
    for uid in list(getattr(game, "participant_ids", []) or []):
        suid = _safe_uid(uid)
        if suid is not None:
            participant_ids.append(suid)

    return {
        "match_id": str(getattr(game, "match_uuid", "") or ""),
        "game_mode": str(getattr(game, "mode", "") or ""),
        "names": names,
        "finish_order": finish_order,
        "participant_ids": participant_ids,
    }


def _fetch_points_awarded(match_id: str) -> Dict[int, int]:
    if not match_id:
        return {}
    db = get_database()
    if db is None:
        return {}
    try:
        row = db.matches.find_one({"_id": match_id}, projection=["points_awarded"])
        raw = (row or {}).get("points_awarded") or {}
        out: Dict[int, int] = {}
        if not isinstance(raw, dict):
            return out
        for k, v in raw.items():
            uid = _safe_uid(k)
            if uid is None:
                continue
            out[uid] = int(v or 0)
        return out
    except Exception:
        return {}


def _fetch_user_labels(user_ids: List[int]) -> Dict[int, str]:
    """Resolve best-effort display labels for users present in match summary."""
    out: Dict[int, str] = {}
    ids = []
    for uid in user_ids:
        suid = _safe_uid(uid)
        if suid is not None and suid not in ids:
            ids.append(suid)
    if not ids:
        return out

    db = get_database()
    if db is None:
        return out

    try:
        for row in db.users.find(
            {"_id": {"$in": ids}},
            projection=["_id", "display_name", "username"],
        ):
            uid = _safe_uid(row.get("_id"))
            if uid is None:
                continue
            label = (row.get("display_name") or "").strip()
            if not label:
                uname = (row.get("username") or "").strip()
                if uname:
                    label = "@%s" % uname
            if label:
                out[uid] = label
    except Exception:
        pass

    missing = [uid for uid in ids if uid not in out]
    if not missing:
        return out

    try:
        for row in db.player_stats.find(
            {"_id": {"$in": missing}},
            projection=["_id", "display_name", "username"],
        ):
            uid = _safe_uid(row.get("_id"))
            if uid is None or uid in out:
                continue
            label = (row.get("display_name") or "").strip()
            if not label:
                uname = (row.get("username") or "").strip()
                if uname:
                    label = "@%s" % uname
            if label:
                out[uid] = label
    except Exception:
        pass

    return out


async def send_post_match_scoreboard(bot, chat_id: int, ctx: Dict[str, Any]) -> None:
    """
    Send compact match score summary and provide a one-tap leaderboard button.
    """
    if not ctx:
        return
    names: Dict[int, str] = dict(ctx.get("names") or {})
    points = _fetch_points_awarded(str(ctx.get("match_id") or ""))

    ordered: List[int] = []
    for uid in list(ctx.get("finish_order") or []):
        if uid not in ordered:
            ordered.append(uid)
    for uid in list(ctx.get("participant_ids") or []):
        if uid not in ordered:
            ordered.append(uid)
    for uid in sorted(set(list(names.keys()) + list(points.keys()))):
        if uid not in ordered:
            ordered.append(uid)

    if not ordered:
        return

    # Enrich missing names from persisted profiles so results do not degrade
    # to "Player <uid>" when someone is no longer in runtime player objects.
    labels = _fetch_user_labels(ordered)
    for uid in ordered:
        if not names.get(uid) and labels.get(uid):
            names[uid] = labels[uid]

    lines = []
    medals = ("🥇", "🥈", "🥉")
    for i, uid in enumerate(ordered):
        label = names.get(uid) or ("Player %d" % uid)
        medal = medals[i] if i < 3 else "▫️"
        score = int(points.get(uid, 0))
        score_text = "%+d" % score
        lines.append("%s %s — <code>%s</code>" % (medal, _name_link(uid, label), score_text))

    title = menu_title_bar("🏁", "Match Scores")
    mode = html.escape(str(ctx.get("game_mode") or "classic"))
    text = "%s\n%s: <b>%s</b>\n\n%s" % (
        title,
        smallcaps("Mode"),
        mode,
        "\n".join(lines),
    )

    await send_message(
        bot,
        chat_id,
        text=text,
        parse_mode="HTML",
        reply_markup=markup(
            [
                [
                    btn_callback(
                        smallcaps("Open Leaderboard"),
                        "ss|lbg",
                        "success",
                        "p18",
                    )
                ]
            ]
        ),
    )

