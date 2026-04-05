#!/usr/bin/env python3
"""Module: Members with frozen/on-hold memberships."""

import logging


from modules._helpers import fmt, safe_list, get_paginated, date_he

logger = logging.getLogger(__name__)

MODULE_META = {
    "id": "members_on_hold",
    "name_he": "מנויים מוקפאים",
    "description_he": "מתאמנים עם מנוי מוקפא כרגע",
    "default_enabled": False,
    "supports_compare": False,
    "default_params": {},
}


def collect(api_key, week_start, month_start, today, params):
    """Fetch members on hold report."""
    rows = get_paginated(api_key, "membersOnHoldReport")

    return {
        "on_hold_count": len(rows),
    }


def format(data, compare_data=None):
    """Format on-hold data as Hebrew Telegram lines."""
    lines = ["<b>── מנויים מוקפאים ──</b>"]

    count = data.get("on_hold_count", 0)
    lines.append(f"מנויים מוקפאים כרגע: <b>{count}</b>")

    return lines
