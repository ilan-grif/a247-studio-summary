#!/usr/bin/env python3
"""Revenue module — memberships sold and revenue tracking."""

from modules._helpers import fmt, get_paginated

MODULE_META = {
    "id": "revenue",
    "name_he": "הכנסות",
    "description_he": "מנויים שנמכרו והכנסות",
    "default_enabled": True,
    "supports_compare": True,
    "default_params": {},
}


def collect(api_key, week_start, month_start, today, params):
    month_str = fmt(month_start)
    week_str = fmt(week_start)

    sales = get_paginated(api_key, "salesReport",
                          fromDate=month_str, toDate=fmt(today))

    sold_week = sold_month = 0
    revenue_week = revenue_month = 0.0

    for s in sales:
        sale_date = s.get("date", "")
        price = float(s.get("price") or 0)
        if sale_date >= month_str:
            sold_month += 1
            revenue_month += price
        if sale_date >= week_str:
            sold_week += 1
            revenue_week += price

    return {
        "sold_week": sold_week,
        "sold_month": sold_month,
        "revenue_week": round(revenue_week),
        "revenue_month": round(revenue_month),
    }


def format(data, compare_data=None):
    lines = []
    lines.append("<b>── הכנסות ──</b>")

    sw = data.get("sold_week", 0)
    sm = data.get("sold_month", 0)
    rw = data.get("revenue_week", 0)
    rm = data.get("revenue_month", 0)

    line = f"מנויים שנמכרו: <b>{sw}</b> (₪{rw:,}) השבוע | <b>{sm}</b> (₪{rm:,}) החודש"
    if compare_data:
        prev_rm = compare_data.get("revenue_month", 0)
        if prev_rm:
            arrow = "↑" if rm > prev_rm else "↓" if rm < prev_rm else "→"
            line += f" {arrow} מ-₪{prev_rm:,}"
    lines.append(line)

    return lines
