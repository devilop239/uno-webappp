# -*- coding: utf-8 -*-
"""Compatibility: menus live in `handlers.menus`."""

from handlers.menus import router as menus_router, send_private_menu

__all__ = ["menus_router", "send_private_menu"]


def register(*_args, **_kwargs) -> None:
    raise RuntimeError(
        "PTB removed: include `handlers.menus.router` on the Aiogram dispatcher (see main.py)."
    )
