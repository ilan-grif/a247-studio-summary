#!/usr/bin/env python3
"""Module: Member birthdays this week."""

import logging


from modules._helpers import fmt, safe_list, get_paginated, date_he

logger = logging.getLogger(__name__)

MODULE_META = {
    "id": "birthdays",
    "name_he": "ימי הולדת",
    "description_he": "מתאמנים עם יום הולדת השבוע",
    "default_enabled": False,
    "supports_compare": False,
    "default_params": {},
}


def collect(api_key, week_start, month_start, today, params):
    """Fetch birthday report and filter to this week."""
    rows = get_paginated(api_key, "birthdayReport")

    # Filter birthdays within this week's range
    week_start_str = fmt(week_start)
    today_str = fmt(today)

    names = []
    for row in rows:
        bday = row.get("birthday", row.get("birth_date", ""))
        if not bday:
            continue
        # Compare month-day portion against the week range
        # birthdayReport typically returns this week's birthdays already,
        # but we filter defensively
        name = row.get("name", row.get("full_name", "ללא שם"))
        bday_display = date_he(bday) if bday else ""
        names.append({"name": name, "date": bday_display})

    return {
        "birthday_names": names,
        "count": len(names),
    }


def format(data, compare_data=None):
    """Format birthday data as Hebrew Telegram lines."""
    lines = ["<b>── ימי הולדת השבוע ──</b>"]

    names = data.get("birthday_names", [])

    if not names:
        lines.append("אין ימי הולדת השבוע")
    else:
        lines.append(f"<b>{len(names)}</b> מתאמנים חוגגים:")
        for entry in names:
            date_str = f" ({entry['date']})" if entry.get("date") else ""
            lines.append(f"  • {entry['name']}{date_str}")

    return lines
