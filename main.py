#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# UNO Telegram bot — Aiogram 3 entry.
#
# Do not run two pollers on the same TOKEN (another process, or webhook).
#
# This program is free software under the GNU AGPL v3+.

from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import ErrorEvent, BotCommand

from config import TOKEN
from db.mongo_client import init_mongo
from handlers import root_router
from loggers import notify_bot_deployed
from middlewares import AuditMiddleware
from tg.runtime import set_bot_ref
from startup_console import (
    boot_backend_live,
    boot_bot_ok,
    boot_bot_starting,
    boot_data_loading,
    boot_data_ok,
    boot_init,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


@root_router.errors()
async def errors_handler(event: ErrorEvent) -> None:
    err = event.exception
    if err is None:
        return
    if isinstance(err, TelegramBadRequest):
        es = str(err).lower()
        if "too old" in es or "query is invalid" in es or "query_id_invalid" in es:
            return
    logger.error("Exception while handling an update", exc_info=err)


async def _run() -> None:
    if not TOKEN:
        logger.error("TOKEN is missing. Set TOKEN or config.json before starting.")
        sys.exit(1)

    bot = Bot(
        token=TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    set_bot_ref(bot)
    dp = Dispatcher()
    dp.update.outer_middleware(AuditMiddleware())
    dp.include_router(root_router)


    @dp.startup()
    async def _on_audit_startup(bot: Bot) -> None:
        await notify_bot_deployed(bot)
        # Register bot commands
        commands = [
            BotCommand(command="status", description="Game snapshot (read-only)"),
            BotCommand(command="new", description="Create a new game"),
            BotCommand(command="teamnew", description="Create a new team game"),
            BotCommand(command="teamname", description="Set team name"),
            BotCommand(command="join", description="Join the game"),
            BotCommand(command="leave", description="Leave the game"),
            BotCommand(command="start", description="Start the game"),
            BotCommand(command="close", description="Close the lobby"),
            BotCommand(command="cancel_lobby", description="Cancel lobby before match starts"),
            BotCommand(command="open", description="Open the lobby"),
            BotCommand(command="kick", description="Kick a player"),
            BotCommand(command="expel", description="Expel a player"),
            BotCommand(command="kill", description="Kill the game"),
            BotCommand(command="handsize", description="Set starting hand size"),
            BotCommand(command="skip", description="Skip current player"),
            BotCommand(command="notify_me", description="Get notified when game starts"),
            BotCommand(command="modes", description="Show available game modes"),
            BotCommand(command="help", description="Show help message"),
            BotCommand(command="rules", description="Show game rules"),
            BotCommand(command="rules_map", description="Show rules map"),
            BotCommand(command="source", description="Get source code"),
            BotCommand(command="news", description="Show latest news"),
            BotCommand(command="stats", description="Show your stats"),
            BotCommand(command="mystats", description="Show your detailed stats"),
            BotCommand(command="points", description="Show your points"),
            BotCommand(command="history", description="Show your match history"),
            BotCommand(command="leaderboard", description="Show global leaderboard"),
            BotCommand(command="weeklylb", description="Show weekly leaderboard"),
            BotCommand(command="monthlylb", description="Show monthly leaderboard"),
            BotCommand(command="seasonlb", description="Show season leaderboard"),
            BotCommand(command="privatenew", description="Create a private game"),
            BotCommand(command="joincode", description="Join a private game with code"),
            BotCommand(command="cancelprivate", description="Cancel private game"),
            BotCommand(command="start_match", description="Start private match"),
            BotCommand(command="start_game", description="Start private game"),
            # Broadcast commands are owner/sudo-only; omit from public menu (still work when typed).

        ]
        await bot.set_my_commands(commands)

    boot_bot_starting()
    boot_bot_ok()
    boot_backend_live()
    try:
        # Avoid replaying stale queued updates after restarts/deploys.
        # This prevents old commands (e.g., /settings in groups) from
        # being processed on startup and sending confusing messages.
        await dp.start_polling(bot, drop_pending_updates=True)
    finally:
        set_bot_ref(None)
        await bot.session.close()


def main() -> None:
    boot_init()
    boot_data_loading()
    init_mongo()
    boot_data_ok()

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        logger.info("Stopping (KeyboardInterrupt).")


if __name__ == "__main__":
    main()
