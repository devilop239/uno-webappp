# -*- coding: utf-8 -*-
"""ISO week / month buckets for rolling leaderboards."""

from datetime import datetime, timezone


def utc_now():
    return datetime.now(timezone.utc)


def week_bucket(dt=None):
    dt = dt or utc_now()
    iso = dt.isocalendar()
    return "%d-W%02d" % (iso[0], iso[1])


def month_bucket(dt=None):
    dt = dt or utc_now()
    return dt.strftime("%Y-%m")
