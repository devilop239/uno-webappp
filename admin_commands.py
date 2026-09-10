# -*- coding: utf-8 -*-
"""Compatibility: admin commands live in `handlers.admin`."""

from handlers.admin import router as admin_router

__all__ = ["admin_router"]


def register(*_args, **_kwargs) -> None:
    raise RuntimeError(
        "PTB removed: include `handlers.admin.router` on the Aiogram dispatcher (see main.py)."
    )
