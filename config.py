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


import os
import json

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    with open("config.json", "r") as f:
        config = json.load(f)
except FileNotFoundError:
    config = {}

TOKEN = os.getenv("TOKEN", config.get("token"))
WORKERS = int(os.getenv("WORKERS", config.get("workers", 32)))
ADMIN_LIST = os.getenv("ADMIN_LIST", config.get("admin_list", None))
DM_START_BOT_USERNAME = str(
    os.getenv("DM_START_BOT_USERNAME", config.get("dm_start_bot_username", "unor0bot"))
).strip().lstrip("@") or "unor0bot"

if isinstance(ADMIN_LIST, str):
    ADMIN_LIST = set(int(x) for x in ADMIN_LIST.split())

# Default bot owner user ID used for owner-only commands.
DEFAULT_BOT_OWNER_ID = 5669044543

# Bot owner user IDs (add_sudo / remove_sudo / all_sudo). If empty, ADMIN_LIST is treated as owners.
_bot_owners_env = os.getenv("BOT_OWNER_IDS", "").strip()
if _bot_owners_env:
    BOT_OWNER_IDS = set()
    for part in _bot_owners_env.replace(",", " ").split():
        part = part.strip()
        if part.lstrip("-").isdigit():
            BOT_OWNER_IDS.add(int(part))
    if not BOT_OWNER_IDS:
        BOT_OWNER_IDS = {DEFAULT_BOT_OWNER_ID}
elif config.get("bot_owner_ids") is not None:
    try:
        BOT_OWNER_IDS = set(int(x) for x in config["bot_owner_ids"])
    except (TypeError, ValueError):
        BOT_OWNER_IDS = {DEFAULT_BOT_OWNER_ID}
else:
    BOT_OWNER_IDS = {DEFAULT_BOT_OWNER_ID}

# Always keep the primary owner ID enabled for owner-only commands.
BOT_OWNER_IDS.add(DEFAULT_BOT_OWNER_ID)

OPEN_LOBBY = os.getenv("OPEN_LOBBY", config.get("open_lobby", True))

if isinstance(OPEN_LOBBY, str):
    OPEN_LOBBY = OPEN_LOBBY.lower() in ("yes", "true", "t", "1")

DEFAULT_GAMEMODE = os.getenv("DEFAULT_GAMEMODE", config.get("default_gamemode", "fast"))
# Turn grace for /skip gating (non–current players wait this long after turn start).
# Penalty removal should stay ~1/6 of grace so behavior matches legacy 120/20 tuning.
WAITING_TIME = int(os.getenv("WAITING_TIME", config.get("waiting_time", 30)))
TIME_REMOVAL_AFTER_SKIP = int(
    os.getenv("TIME_REMOVAL_AFTER_SKIP", config.get("time_removal_after_skip", 5))
)
MIN_FAST_TURN_TIME = int(os.getenv("MIN_FAST_TURN_TIME", config.get("min_fast_turn_time", 15)))
MIN_PLAYERS = int(os.getenv("MIN_PLAYERS", config.get("min_players", 2)))

# Styled inline keys (Telegram Bot API: style + icon_custom_emoji_id). Override via env JSON or config.json.
_INLINE_STYLES_ENV = os.getenv("INLINE_BUTTON_STYLES", "")
if _INLINE_STYLES_ENV:
    INLINE_BUTTON_STYLES = _INLINE_STYLES_ENV.lower() in ("1", "true", "yes", "on")
else:
    INLINE_BUTTON_STYLES = bool(config.get("inline_button_styles", True))

_DEFAULT_BUTTON_EMOJI_IDS = {
    "primary_btn": "5938413566624272793",
    "success_btn": "5960608239623082921",
    "danger_btn": "5213391561999526028",
    "default_btn": "6181683177149435931",
    "emoji_btn": "6179375809048875316",
    "owner_btn": "5807868868886009920",
}
_emj = os.getenv("BUTTON_EMOJI_IDS_JSON")
if _emj:
    try:
        BUTTON_EMOJI_IDS = json.loads(_emj)
    except json.JSONDecodeError:
        BUTTON_EMOJI_IDS = dict(_DEFAULT_BUTTON_EMOJI_IDS)
elif config.get("button_emoji_ids"):
    BUTTON_EMOJI_IDS = dict(config["button_emoji_ids"])
else:
    BUTTON_EMOJI_IDS = dict(_DEFAULT_BUTTON_EMOJI_IDS)

# Extended premium emoji IDs (rotate in UI); keys p1..p22 — override via BUTTON_EMOJI_IDS_JSON.
_PREMIUM_IDS = [
    "5938413566624272793",
    "5960608239623082921",
    "5213391561999526028",
    "5994495149336434048",
    "5836907383292436018",
    "6179375809048875316",
    "5415825426633202840",
    "6073125993252393445",
    "6070895054094864624",
    "6073456529640525999",
    "6073220916324602224",
    "6181690847961027504",
    "5327869427033585919",
    "5231012545799666522",
    "5456140674028019486",
    "5327928143531486985",
    "5328306933877193964",
    "5328295947350848665",
    "5220108512893344933",
    "5807868868886009920",
    "6073117703965511893",
    "6073459905484821185",
]
for _i, _pid in enumerate(_PREMIUM_IDS, start=1):
    BUTTON_EMOJI_IDS.setdefault("p%d" % _i, _pid)
BUTTON_EMOJI_IDS.setdefault("owner_btn", _DEFAULT_BUTTON_EMOJI_IDS["owner_btn"])
BUTTON_EMOJI_IDS.setdefault("rules_btn", "5936130851635990622")
# Hand size picker custom emoji IDs
BUTTON_EMOJI_IDS.setdefault("hs_7", "6311849260635656729")
BUTTON_EMOJI_IDS.setdefault("hs_14", "6314575950688293716")
BUTTON_EMOJI_IDS.setdefault("hs_21", "6314237464315696206")
BUTTON_EMOJI_IDS.setdefault("bck_21", "5888484185261216745")
BUTTON_EMOJI_IDS.setdefault("sttg_21", "5904258298764334001")
BUTTON_EMOJI_IDS.setdefault("wld", "5994495149336434048")
BUTTON_EMOJI_IDS.setdefault("rbw", "5936130851635990622")
BUTTON_EMOJI_IDS.setdefault("sdth", "5819078828017849357")
BUTTON_EMOJI_IDS.setdefault("deck", "5904258298764334001")
BUTTON_EMOJI_IDS.setdefault("nrml", "5836907383292436018")

# --- MongoDB (persistent stats, users, matches; optional for local dev) ---
MONGO_URI = os.getenv("MONGO_URI", config.get("mongo_uri", "") or "").strip()
_mdb = os.getenv("MONGO_DB_NAME", config.get("mongo_db_name", "") or "").strip()
MONGO_DB_NAME = _mdb or "uno_bot"

# --- Audit / ops log group (Telegram): JSON events mirrored here when enabled ---
def _log_group_id() -> int:
    raw = os.getenv("LOG_GROUP_ID", "").strip()
    if raw:
        try:
            return int(raw)
        except ValueError:
            pass
    c = config.get("log_group_id")
    if c is not None and str(c).strip() != "":
        try:
            return int(c)
        except (TypeError, ValueError):
            pass
    return -1003233311003


LOG_GROUP_ID = _log_group_id()
_LOG_TG = os.getenv("LOG_TELEGRAM_ENABLED", "true").strip().lower()
LOG_TELEGRAM_ENABLED = _LOG_TG in ("1", "true", "yes", "on")

# --- Points, season & match validation ---
# Defaults are defined here. Override with environment variables (UPPER_SNAKE) or
# config.json keys (lowercase, e.g. win_points). You do not need a long .env block.

DEFAULT_STATS_SEASON_ID = "default"

DEFAULT_WIN_POINTS = 120
DEFAULT_PARTICIPATION_POINTS = 25
DEFAULT_SECOND_PLACE_POINTS = 45
DEFAULT_THIRD_PLACE_POINTS = 30
DEFAULT_STREAK_BONUS_3 = 15
DEFAULT_STREAK_BONUS_5 = 35
DEFAULT_LARGE_MATCH_BONUS = 20
DEFAULT_SUDDEN_DEATH_WIN_POINTS = 180
DEFAULT_SUDDEN_DEATH_PARTICIPATION_POINTS = 15
DEFAULT_LARGE_MATCH_MIN_PLAYERS = 5
DEFAULT_ABANDON_PENALTY = 40
DEFAULT_MIN_VALID_PLAYERS_FOR_POINTS = 2
DEFAULT_MIN_VALID_TURNS_FOR_POINTS = 1


def _season_id() -> str:
    """Season label for season_points / /seasonlb (empty env falls back to default)."""
    for key in ("STATS_SEASON_ID", "S_SEASON_ID"):
        raw = os.getenv(key)
        if raw is not None and str(raw).strip() != "":
            return str(raw).strip()
    c = config.get("stats_season_id")
    if c is not None and str(c).strip() != "":
        return str(c).strip()
    return DEFAULT_STATS_SEASON_ID


SEASON_ID = _season_id()


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is not None and str(raw).strip() != "":
        try:
            return int(raw)
        except ValueError:
            return int(default)
    c = config.get(name.lower())
    if c is not None and str(c).strip() != "":
        try:
            return int(c)
        except (TypeError, ValueError):
            return int(default)
    return int(default)


WIN_POINTS = _int_env("WIN_POINTS", DEFAULT_WIN_POINTS)
PARTICIPATION_POINTS = _int_env("PARTICIPATION_POINTS", DEFAULT_PARTICIPATION_POINTS)
SECOND_PLACE_POINTS = _int_env("SECOND_PLACE_POINTS", DEFAULT_SECOND_PLACE_POINTS)
THIRD_PLACE_POINTS = _int_env("THIRD_PLACE_POINTS", DEFAULT_THIRD_PLACE_POINTS)
STREAK_BONUS_3 = _int_env("STREAK_BONUS_3", DEFAULT_STREAK_BONUS_3)
STREAK_BONUS_5 = _int_env("STREAK_BONUS_5", DEFAULT_STREAK_BONUS_5)
LARGE_MATCH_BONUS = _int_env("LARGE_MATCH_BONUS", DEFAULT_LARGE_MATCH_BONUS)
SUDDEN_DEATH_WIN_POINTS = _int_env("SUDDEN_DEATH_WIN_POINTS", DEFAULT_SUDDEN_DEATH_WIN_POINTS)
SUDDEN_DEATH_PARTICIPATION_POINTS = _int_env("SUDDEN_DEATH_PARTICIPATION_POINTS", DEFAULT_SUDDEN_DEATH_PARTICIPATION_POINTS)
LARGE_MATCH_MIN_PLAYERS = _int_env("LARGE_MATCH_MIN_PLAYERS", DEFAULT_LARGE_MATCH_MIN_PLAYERS)
ABANDON_PENALTY = _int_env("ABANDON_PENALTY", DEFAULT_ABANDON_PENALTY)
MIN_VALID_PLAYERS_FOR_POINTS = _int_env(
    "MIN_VALID_PLAYERS_FOR_POINTS", DEFAULT_MIN_VALID_PLAYERS_FOR_POINTS
)
MIN_VALID_TURNS_FOR_POINTS = 1  # Force to 1 to allow points in all games
