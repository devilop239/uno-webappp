"""
Optional extra messages after /help (disabled by default).
"""

import asyncio
import logging
import random

from aiogram import Bot
from aiogram.enums import ParseMode

from tg.runtime import get_bot_ref

logger = logging.getLogger(__name__)

PROMOTIONS = {}


def get_promotion():
    if not PROMOTIONS:
        return None
    return random.choices(
        list(PROMOTIONS.keys()),
        weights=list(PROMOTIONS.values()),
    )[0]


async def send_promotion(bot: Bot, chat_id: int, chance: float = 1.0) -> None:
    msg = get_promotion()
    if msg and random.random() <= chance:
        try:
            await bot.send_message(chat_id, msg, parse_mode=ParseMode.HTML)
        except Exception:
            logger.exception("send_promotion failed")


def send_promotion_async(chat, chance: float = 1.0) -> None:
    """
    Called from sync code (e.g. game_manager.end_game) while the polling loop runs.
    Best-effort; no-op if bot ref is unset or no event loop.
    """
    if not PROMOTIONS:
        return
    bot = get_bot_ref()
    cid = getattr(chat, "id", None)
    if bot is None or cid is None:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return

    async def _run():
        await send_promotion(bot, int(cid), chance=chance)

    loop.create_task(_run())
