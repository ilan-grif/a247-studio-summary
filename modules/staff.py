#!/usr/bin/env python3
"""Module: Staff / instructor attendance."""

import logging


from modules._helpers import fmt, safe_list, get_paginated, date_he

logger = logging.getLogger(__name__)

MODULE_META = {
    "id": "staff",
    "name_he": "צוות מדריכים",
    "description_he": "נוכחות צוות מדריכים והיעדרויות",
    "default_enabled": False,
    "supports_compare": False,
    "default_params": {},
}


def collect(api_key, week_start, month_start, today, params):
    """Fetch employee attendance report."""
    rows = get_paginated(
        api_key, "employeeAttendanceReport",
        fromDate=fmt(week_start), toDate=fmt(today),
    )

    instructor_count = len(rows)
    no_shows = []
    for row in rows:
        status = row.get("status", "").lower()
        attended = row.get("attended", row.get("check_in", ""))
        if status in ("absent", "no_show") or attended in ("No", "no", False):
            name = row.get("name", row.get("employee_name", "ללא שם"))
            no_shows.append(name)

    return {
        "instructor_count": instructor_count,
        "no_shows": no_shows,
    }


def format(data, compare_data=None):
    """Format staff data as Hebrew Telegram lines."""
    lines = ["<b>── צוות מדריכים ──</b>"]

    count = data.get("instructor_count", 0)
    no_shows = data.get("no_shows", [])

    if no_shows:
        lines.append(f"מדריכים השבוע: <b>{count}</b> | חסרים: <b>{len(no_shows)}</b>")
        for name in no_shows:
            lines.append(f"  • {name} — לא הגיע/ה")
    else:
        lines.append(f"מדריכים השבוע: <b>{count}</b> — כולם נוכחים ✓")

    return lines
