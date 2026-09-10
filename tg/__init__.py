# -*- coding: utf-8 -*-
"""Aiogram-specific helpers (safe API calls). Used by the new runtime; PTB code keeps using utils.py."""

from tg.helpers import answer_callback_query_safe, safe_edit_message_text

__all__ = ["answer_callback_query_safe", "safe_edit_message_text"]
