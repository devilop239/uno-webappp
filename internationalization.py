# -*- coding: utf-8 -*-
"""
Pure English string pass-through module.
Replaces gettext catalog loading with lightweight string formatting.
"""

from functools import wraps


class _Underscore:
    """Lightweight pass-through string formatter."""
    def push(self, locale):
        pass

    def pop(self):
        return None

    @property
    def code(self):
        return "en_US"

    def __call__(self, singular, plural=None, n=1, locale=None):
        if n == 1 or plural is None:
            return singular
        return plural


_ = _Underscore()


def __(singular, plural=None, n=1, multi=False):
    """Pass-through string translation."""
    return _(singular, plural, n)


def user_locale(func):
    @wraps(func)
    def wrapped(update, context, *pargs, **kwargs):
        return func(update, context, *pargs, **kwargs)
    return wrapped


def game_locales(func):
    @wraps(func)
    def wrapped(update, context, *pargs, **kwargs):
        return func(update, context, *pargs, **kwargs)
    return wrapped


def _chat_id_from_inline_result_id(result_id):
    parts = str(result_id).split(":")
    if len(parts) >= 3:
        try:
            return int(parts[-1])
        except ValueError:
            return None
    return None


class _ChatRef:
    __slots__ = ("id",)

    def __init__(self, chat_id):
        self.id = chat_id


def push_game_locales_for_user_chat(user, chat) -> int:
    return 0


def pop_locale_stack_n(n: int) -> None:
    pass


def user_chat_for_chosen_inline_result(cir) -> tuple:
    user = cir.from_user
    chat = None
    rid = getattr(cir, "result_id", None)
    if rid:
        cid = _chat_id_from_inline_result_id(rid)
        if cid is not None:
            chat = _ChatRef(cid)
    if chat is None:
        from shared_vars import gm
        if user.id in gm.userid_current:
            chat = gm.userid_current.get(user.id).game.chat
    return user, chat

