#!/usr/bin/env python3
"""Operations module — class fill rates."""

from modules._helpers import fmt, get_paginated, date_he

MODULE_META = {
    "id": "operations",
    "name_he": "שיעורים קבוצתיים",
    "description_he": "תפוסת שיעורים ונוכחות",
    "default_enabled": True,
    "supports_compare": False,
    "default_params": {"low_fill_pct": 50},
}


def collect(api_key, week_start, month_start, today, params):
    low_fill_pct = params.get("low_fill_pct", 50)
    week_str = fmt(week_start)
    today_str = fmt(today)

    classes = get_paginated(api_key, "classesSummaryReport",
                            fromDate=week_str, toDate=today_str)

    # Filter: active group classes only.
    # Arbox mislabels some personal training as service_type="class"
    group_classes = [
        c for c in classes
        if c.get("status") == "active"
        and c.get("service_type") != "appointment"
        and "אימון אישי" not in (c.get("class_name") or "")
        and "חסימת זמן" not in (c.get("class_name") or "")
    ]

    low_fill = []
    for c in group_classes:
        reg_pct = float(c.get("registration_percentage") or 0)
        if reg_pct < low_fill_pct:
            low_fill.append({
                "class_name": c.get("class_name", "Unknown"),
                "date": c.get("date", ""),
                "time": c.get("start_time", ""),
                "registered": int(c.get("registration_count") or 0),
                "fill_pct": round(reg_pct),
                "checked_in": int(c.get("check_in") or 0),
                "instructor": c.get("staff_member", ""),
            })
    low_fill.sort(key=lambda x: x["fill_pct"])

    return {
        "total_group_classes": len(group_classes),
        "low_fill_classes": low_fill[:10],
        "low_fill_count": len(low_fill),
    }


def format(data, compare_data=None):
    lines = []
    total_classes = data.get("total_group_classes", 0)
    low_fill = data.get("low_fill_classes", [])
    low_count = data.get("low_fill_count", 0)

    if total_classes > 0:
        lines.append("<b>── שיעורים קבוצתיים ──</b>")
        if low_count > 0:
            lines.append(f"שיעורים מתחת ל-50% תפוסה: <b>{low_count}</b> מתוך {total_classes}")
            for c in low_fill[:5]:
                lines.append(
                    f"  • {c['class_name']} ({date_he(c.get('date', ''))} {c.get('time', '')}) — "
                    f"{c['fill_pct']}% ({c['registered']} נרשמו)"
                )
            if low_count > 5:
                lines.append(f"  ... ועוד {low_count - 5}")
        else:
            lines.append(f"כל {total_classes} השיעורים מעל 50% תפוסה")

    return lines
