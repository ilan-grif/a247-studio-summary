#!/usr/bin/env python3
"""Module: Membership renewals and future memberships forecast."""

import logging


from modules._helpers import fmt, safe_list, get_paginated, date_he

logger = logging.getLogger(__name__)

MODULE_META = {
    "id": "renewals_forecast",
    "name_he": "חידושים ותחזית",
    "description_he": "חידושי מנויים החודש ומנויים עתידיים",
    "default_enabled": True,
    "supports_compare": False,
    "default_params": {},
}


def collect(api_key, week_start, month_start, today, params):
    """Fetch renewals this month and future memberships."""
    # Renewals this month
    renewals = get_paginated(
        api_key, "renewalsReport",
        fromDate=fmt(month_start), toDate=fmt(today),
    )

    # Future memberships
    future = get_paginated(
        api_key, "futureMembershipsReport",
    )

    return {
        "renewals_count": len(renewals),
        "future_memberships_count": len(future),
    }


def format(data, compare_data=None):
    """Format renewals/forecast data as Hebrew Telegram lines."""
    lines = ["<b>── חידושים ותחזית ──</b>"]

    renewals = data.get("renewals_count", 0)
    future = data.get("future_memberships_count", 0)

    lines.append(f"חידושים החודש: <b>{renewals}</b>")
    lines.append(f"מנויים עתידיים: <b>{future}</b>")

    return lines
