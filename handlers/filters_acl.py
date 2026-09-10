# -*- coding: utf-8 -*-
"""Private-chat ACL filters (sudo / owner)."""

from aiogram.filters import BaseFilter
from aiogram.types import Message

from services import admin_acl


class SudoPrivateFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        u = message.from_user
        return bool(
            message.chat
            and message.chat.type == "private"
            and u
            and admin_acl.is_sudo(u.id)
        )


class OwnerPrivateFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        u = message.from_user
        return bool(
            message.chat
            and message.chat.type == "private"
            and u
            and admin_acl.is_owner(u.id)
        )
