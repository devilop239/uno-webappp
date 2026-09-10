# -*- coding: utf-8 -*-
"""Holds the running Aiogram Bot for sync code that schedules fire-and-forget tasks."""

from __future__ import annotations

from typing import Optional

from aiogram import Bot

_bot_ref: Optional[Bot] = None


def set_bot_ref(bot: Optional[Bot]) -> None:
    global _bot_ref
    _bot_ref = bot


def get_bot_ref() -> Optional[Bot]:
    return _bot_ref
