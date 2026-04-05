#!/usr/bin/env python3
"""Expiring memberships module — memberships about to lapse."""

from datetime import timedelta
from modules._helpers import fmt, get_paginated, date_he

MODULE_META = {
    "id": "expiring",
    "name_he": "מנויים שפג תוקפם",
    "description_he": "מנויים שעומדים לפוג בקרוב ולא חידשו",
    "default_enabled": True,
    "supports_compare": False,
    "default_params": {"expiry_days": 14},
}


def collect(api_key, week_start, month_start, today, params):
    expiry_days = params.get("expiry_days", 14)
    today_str = fmt(today)
    expiry_end = fmt(today + timedelta(days=expiry_days))

    expiring = get_paginated(api_key, "expiringMembershipsReport",
                             fromDate=today_str, toDate=expiry_end)

    members = []
    for e in expiring:
        members.append({
            "name": e.get("name", "Unknown"),
            "end_date": e.get("end_date", ""),
            "membership": e.get("membership_type_name", ""),
            "has_future": e.get("has_future_membership", "no"),
        })

    not_renewed = [m for m in members if m["has_future"] != "yes"]
    not_renewed.sort(key=lambda x: x["end_date"])

    return {
        "expiring_members": not_renewed[:15],
        "expiring_count": len(not_renewed),
        "already_renewed": len(members) - len(not_renewed),
    }


def format(data, compare_data=None):
    lines = []
    exp_count = data.get("expiring_count", 0)
    renewed = data.get("already_renewed", 0)

    if exp_count > 0:
        lines.append(f"מנויים שעומדים לפוג ב-14 יום: <b>{exp_count}</b> (לא חידשו)")
        if renewed > 0:
            lines.append(f"  ({renewed} נוספים כבר חידשו)")
        for m in data.get("expiring_members", [])[:5]:
            end = date_he(m.get("end_date", ""))
            membership = m.get("membership", "")
            lines.append(f"  • {m['name']} — {end} ({membership})")
        if exp_count > 5:
            lines.append(f"  ... ועוד {exp_count - 5}")
    else:
        lines.append("מנויים שפג תוקפם בקרוב: <b>0</b>")

    return lines
