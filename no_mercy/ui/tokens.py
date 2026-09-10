"""Short-lived UI tokens embedded in callback_data."""
from __future__ import annotations

import secrets
from dataclasses import dataclass

from no_mercy.ui import config as ui_cfg


@dataclass(frozen=True)
class ParsedCallback:
    action: str
    token: str
    arg: str | None


def refresh_ui_token(game) -> str:
    token = secrets.token_hex(4)
    game.mercy_ui_token = token
    return token


def token_matches(game, token: str) -> bool:
    return bool(token) and token == getattr(game, "mercy_ui_token", None)


def build_callback(action: str, game, arg: str | None = None) -> str:
    token = getattr(game, "mercy_ui_token", None) or refresh_ui_token(game)
    parts = [ui_cfg.CB_PREFIX, action, token]
    if arg is not None and arg != "":
        parts.append(str(arg))
    data = "|".join(parts)
    if len(data) > 64:
        data = data[:64]
    return data


def parse_callback(data: str) -> ParsedCallback | None:
    if not data or not data.startswith(ui_cfg.CB_PREFIX + "|"):
        return None
    parts = data.split("|")
    if len(parts) < 3:
        return None
    action = parts[1]
    token = parts[2]
    arg = parts[3] if len(parts) > 3 else None
    return ParsedCallback(action=action, token=token, arg=arg)
