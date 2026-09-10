# -*- coding: utf-8 -*-
"""Compatibility: stats hub lives in `handlers.stats`."""

from handlers.stats import router as stats_router

__all__ = ["stats_router"]


def register(*_args, **_kwargs) -> None:
    raise RuntimeError(
        "PTB removed: include `handlers.stats.router` on the Aiogram dispatcher (see main.py)."
    )
