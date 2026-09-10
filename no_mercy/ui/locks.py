"""Per-chat async locks for NO MERCY callback serialization."""
from __future__ import annotations

import asyncio

_locks: dict[int, asyncio.Lock] = {}


def chat_lock(game) -> asyncio.Lock:
    cid = int(game.chat.id)
    if cid not in _locks:
        _locks[cid] = asyncio.Lock()
    return _locks[cid]


def clear_lock(chat_id: int) -> None:
    _locks.pop(int(chat_id), None)
