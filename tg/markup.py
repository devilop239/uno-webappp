# -*- coding: utf-8 -*-
"""Convert `inline_buttons.markup()` dicts to Aiogram keyboard models."""

from __future__ import annotations

from typing import Any, Dict, Optional, Union

from aiogram.types import InlineKeyboardMarkup

MarkupDict = Dict[str, Any]


def reply_markup_from_dict(
    d: Optional[Union[MarkupDict, InlineKeyboardMarkup]],
) -> Optional[InlineKeyboardMarkup]:
    if d is None:
        return None
    if isinstance(d, InlineKeyboardMarkup):
        return d
    return InlineKeyboardMarkup.model_validate(d)
