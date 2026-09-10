# -*- coding: utf-8 -*-
"""Available locales - English only."""

OFFSET = 127462 - ord("A")


def flag(code):
    return chr(ord(code[0]) + OFFSET) + chr(ord(code[1]) + OFFSET)


available_locales = {
    "en_US": flag("US") + " English (US)",
}
