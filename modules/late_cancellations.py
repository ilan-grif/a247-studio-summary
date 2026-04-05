#!/usr/bin/env python3
"""Module: Late cancellation tracking."""

import logging
from collections import Counter


from modules._helpers import fmt, safe_list, get_paginated, date_he

logger = logging.getLogger(__name__)

MODULE_META = {
    "id": "late_cancellations",
    "name_he": "ביטולים מאוחרים",
    "description_he": "ביטולים מאוחרים לפי שבוע וחודש",
    "default_enabled": False,
    "supports_compare": False,
    "default_params": {},
}


def collect(api_key, week_start, month_start, today, params):
    """Fetch late cancellations for week and month."""
    # Week data
    week_rows = get_paginated(
        api_key, "lateCancellationReport",
        fromDate=fmt(week_start), toDate=fmt(today),
    )

    # Month data
    month_rows = get_paginated(
        api_key, "lateCancellationReport",
        fromDate=fmt(month_start), toDate=fmt(today),
    )

    # Top classes by late cancellation count (month)
    class_counter = Counter()
    for row in month_rows:
        class_name = row.get("class_name", row.get("service_name", "לא ידוע"))
        class_counter[class_name] += 1

    top_classes = class_counter.most_common(3)

    return {
        "week_count": len(week_rows),
        "month_count": len(month_rows),
        "top_classes": [{"class_name": name, "count": cnt} for name, cnt in top_classes],
    }


def format(data, compare_data=None):
    """Format late cancellation data as Hebrew Telegram lines."""
    lines = ["<b>── ביטולים מאוחרים ──</b>"]

    week = data.get("week_count", 0)
    month = data.get("month_count", 0)
    top = data.get("top_classes", [])

    lines.append(f"השבוע: <b>{week}</b> | החודש: <b>{month}</b>")

    if top:
        lines.append("")
        lines.append("שיעורים עם הכי הרבה ביטולים:")
        for c in top:
            lines.append(f"  • {c['class_name']} — {c['count']} ביטולים")

    return lines
