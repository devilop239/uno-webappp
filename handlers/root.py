# -*- coding: utf-8 -*-
"""Compose routers. Order matters: admin private /stats before player /stats."""

from aiogram import Router

from handlers.admin import router as admin_router
from handlers.broadcast import router as broadcast_router
from handlers.link import router as link_router
from handlers.game import router as game_router
from handlers.inline import router as inline_router
from handlers.menus import router as menus_router
from handlers.private_mode import router as private_mode_router
from handlers.rules import router as rules_router
from handlers.select import router as select_router
from handlers.service import router as service_router
from handlers.stats import router as stats_router
from settings import settings_router


root_router = Router(name="root")

root_router.include_router(admin_router)
root_router.include_router(link_router)
root_router.include_router(broadcast_router)
root_router.include_router(private_mode_router)
root_router.include_router(stats_router)
root_router.include_router(menus_router)
root_router.include_router(rules_router)
root_router.include_router(settings_router)
root_router.include_router(game_router)
root_router.include_router(inline_router)
root_router.include_router(select_router)
root_router.include_router(service_router)