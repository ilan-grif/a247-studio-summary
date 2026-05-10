#!/usr/bin/env python3
"""Sales by agent module — membership sales grouped by salesperson."""

from modules._helpers import fmt, get_paginated

MODULE_META = {
    "id": "sales_by_agent",
    "name_he": "מכירות לפי איש מכירות",
    "description_he": "מנויים שנמכרו השבוע, מקובצים לפי איש המכירות",
    "default_enabled": True,
    "supports_compare": True,
    "default_params": {
        "membership_keyword": "מנוי",
    },
}


def _is_membership(sale, keyword):
    """A sale is a membership if item_type == 'plan' or item_name contains the Hebrew keyword."""
    item_type = (sale.get("item_type") or "").lower()
    item_name = sale.get("item_name") or ""
    return item_type == "plan" or keyword in item_name


def collect(api_key, week_start, month_start, today, params):
    week_str = fmt(week_start)
    month_str = fmt(month_start)
    keyword = params.get("membership_keyword", "מנוי")

    sales = get_paginated(api_key, "salesReport",
                          fromDate=month_str, toDate=fmt(today))

    by_agent_week = {}
    by_agent_month = {}
    week_total = 0
    month_total = 0

    for s in sales:
        if not _is_membership(s, keyword):
            continue
        sale_date = s.get("date", "")
        agent = (s.get("sale_person_name") or "").strip() or "לא ידוע"
        if sale_date >= month_str:
            by_agent_month[agent] = by_agent_month.get(agent, 0) + 1
            month_total += 1
        if sale_date >= week_str:
            by_agent_week[agent] = by_agent_week.get(agent, 0) + 1
            week_total += 1

    return {
        "week_total": week_total,
        "month_total": month_total,
        "by_agent_week": by_agent_week,
        "by_agent_month": by_agent_month,
    }


def _agent_lines(by_agent):
    return [f"  • {a} — {c}" for a, c in sorted(by_agent.items(), key=lambda x: -x[1])]


def format(data, compare_data=None):
    lines = []
    lines.append("<b>── מכירות לפי איש מכירות ──</b>")

    week_total = data.get("week_total", 0)
    month_total = data.get("month_total", 0)
    by_week = data.get("by_agent_week", {}) or {}
    by_month = data.get("by_agent_month", {}) or {}

    if week_total > 0:
        lines.append(f"השבוע: <b>{week_total}</b>")
        lines.extend(_agent_lines(by_week))
    else:
        lines.append("השבוע: אין מכירות מנויים")

    if month_total > 0:
        lines.append(f"החודש: <b>{month_total}</b>")
        lines.extend(_agent_lines(by_month))

    if compare_data:
        prev_month = compare_data.get("month_total", 0)
        if prev_month:
            arrow = "↑" if month_total > prev_month else "↓" if month_total < prev_month else "→"
            lines.append(f"חודש קודם: {prev_month} {arrow}")

    return lines
