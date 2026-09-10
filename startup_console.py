# -*- coding: utf-8 -*-
"""Startup console lines (small-caps style + flush for immediate display)."""

import sys

_stdio_configured = False


def _ensure_utf8_stdio() -> None:
    """Avoid UnicodeEncodeError on Windows cp1252 consoles when printing ✦ / small caps."""
    global _stdio_configured
    if _stdio_configured:
        return
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (OSError, ValueError, AttributeError):
        pass
    _stdio_configured = True


def _out(line: str) -> None:
    _ensure_utf8_stdio()
    try:
        print(line, flush=True)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", None) or "ascii"
        print(line.encode(enc, errors="replace").decode(enc, errors="replace"), flush=True)


def boot_init() -> None:
    _out("✦ ʙᴏᴛ ɪs ɪɴɪᴛɪᴀʟɪᴢɪɴɢ...")


def boot_mongo_connecting() -> None:
    _out("✦ ᴄᴏɴɴᴇᴄᴛɪɴɢ ᴛᴏ ᴍᴏɴɢᴏᴅʙ...")


def boot_mongo_ok() -> None:
    _out("✦ ᴍᴏɴɢᴏᴅʙ ᴄᴏɴɴᴇᴄᴛᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ")


def boot_mongo_skipped() -> None:
    _out("✦ ᴍᴏɴɢᴏᴅʙ sᴋɪᴘᴘᴇᴅ (ɴᴏ MONGO_URI)")


def boot_mongo_failed() -> None:
    _out("✦ ᴍᴏɴɢᴏᴅʙ ᴄᴏɴɴᴇᴄᴛɪᴏɴ ғᴀɪʟᴇᴅ — sᴇᴇ ʟᴏɢs")


def boot_data_loading() -> None:
    _out("✦ ʟᴏᴀᴅɪɴɢ ᴀʟʟ ᴅᴀᴛᴀ...")


def boot_data_ok() -> None:
    _out("✦ ᴀʟʟ ᴅᴀᴛᴀ ʟᴏᴀᴅᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ")


def boot_bot_starting() -> None:
    _out("✦ ʙᴏᴛ ɪs sᴛᴀʀᴛɪɴɢ...")
    _out(
        "✦ ɪɴʟɪɴᴇ ғᴇᴇᴅʙᴀᴄᴋ: ɪɴ @BᴏᴛFᴀᴛʜᴇʀ sᴇᴛ /setinlinefeedback "
        "ᴏɴ — ᴏᴛʜᴇʀᴡɪsᴇ ᴄᴀʀᴅ ᴘɪᴄᴋs ᴅᴏ ɴᴏᴛ ʀᴇᴀᴄʜ ᴛʜᴇ ʙᴏᴛ (ғᴀsᴛ ᴍᴏᴅᴇ ᴛʜᴇɴ ᴏɴʟʏ ᴀᴜᴛᴏ-sᴋɪᴘs)."
    )


def boot_bot_ok() -> None:
    _out("✦ ʙᴏᴛ sᴛᴀʀᴛᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ")


def boot_backend_live() -> None:
    _out("✦ ʙᴀᴄᴋᴇɴᴅ ɪs ʟɪᴠᴇ")
