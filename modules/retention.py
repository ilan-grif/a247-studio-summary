#!/usr/bin/env python3
"""Retention module — ghost members and cancellations."""

from datetime import timedelta
from modules._helpers import fmt, safe_list, get_paginated, get_bookings, month_start as _month_start

MODULE_META = {
    "id": "retention",
    "name_he": "דגלים אדומים",
    "description_he": "חברים שלא מגיעים, ביטולי מנויים",
    "default_enabled": True,
    "supports_compare": False,
    "default_params": {"ghost_days": 14},
}


def collect(api_key, week_start, month_start, today, params):
    ghost_days = params.get("ghost_days", 14)
    today_str = fmt(today)
    ghost_start = fmt(today - timedelta(days=ghost_days))

    # Active members
    active_members = get_paginated(api_key, "activeMembersReport")

    # Recent bookings for ghost detection
    bookings_list = get_paginated(api_key, "bookingsReport",
                                  fromDate=ghost_start, toDate=today_str)

    recent_visitors = {str(b.get("user_id", "")) for b in bookings_list if b.get("user_id")}

    ghosts = []
    for m in active_members:
        uid = str(m.get("user_id", ""))
        if uid and uid not in recent_visitors:
            ghosts.append({"name": m.get("name", "Unknown"), "user_id": uid})
    ghosts.sort(key=lambda x: x["name"])

    # Cancellations — client-side date filtering
    month_start_str = fmt(_month_start(today))
    all_cancellations = get_paginated(api_key, "canceledMembershipsReport")
    cancellations_month = sum(
        1 for c in all_cancellations
        if (c.get("cancelled_time") or "")[:10] >= month_start_str
    )

    return {
        "total_active": len(active_members),
        "ghost_members": ghosts[:15],
        "ghost_count": len(ghosts),
        "cancellations_month": cancellations_month,
    }


def format(data, compare_data=None):
    lines = []
    lines.append("<b>── דגלים אדומים ──</b>")

    total_active = data.get("total_active", 0)
    ghost_count = data.get("ghost_count", 0)
    cancel_count = data.get("cancellations_month", 0)

    lines.append(f"חברים פעילים: <b>{total_active}</b>")

    if ghost_count > 0:
        lines.append(f"לא הגיעו 14+ יום: <b>{ghost_count}</b>")
        for g in data.get("ghost_members", [])[:7]:
            lines.append(f"  • {g['name']}")
        if ghost_count > 7:
            lines.append(f"  ... ועוד {ghost_count - 7}")
    else:
        lines.append("לא הגיעו 14+ יום: <b>0</b>")

    if cancel_count > 0:
        lines.append(f"ביטולי מנויים החודש: <b>{cancel_count}</b>")

    return lines
