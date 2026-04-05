#!/usr/bin/env python3
"""Module: Outstanding debt report."""

import logging


from modules._helpers import fmt, safe_list, get_paginated, date_he

logger = logging.getLogger(__name__)

MODULE_META = {
    "id": "debt",
    "name_he": "חובות",
    "description_he": "סיכום חובות פתוחים של מתאמנים",
    "default_enabled": False,
    "supports_compare": False,
    "default_params": {"threshold": 200},
}


def collect(api_key, week_start, month_start, today, params):
    """Fetch debt report and compute totals."""
    threshold = params.get("threshold", MODULE_META["default_params"]["threshold"])

    rows = get_paginated(api_key, "debtReport")

    total_debt = 0.0
    debtors = []
    for row in rows:
        amount = float(row.get("debt", 0) or 0)
        if amount <= 0:
            continue
        total_debt += amount
        name = row.get("name", row.get("full_name", "ללא שם"))
        debtors.append({"name": name, "amount": amount})

    # Filter by threshold and sort descending
    debtors_above = [d for d in debtors if d["amount"] >= threshold]
    debtors_above.sort(key=lambda d: d["amount"], reverse=True)

    return {
        "total_debt": total_debt,
        "debtor_count": len(debtors),
        "debtors_above_threshold": debtors_above[:5],
        "threshold": threshold,
    }


def format(data, compare_data=None):
    """Format debt data as Hebrew Telegram lines."""
    lines = ["<b>── חובות ──</b>"]

    total = data.get("total_debt", 0)
    count = data.get("debtor_count", 0)
    threshold = data.get("threshold", 200)
    top = data.get("debtors_above_threshold", [])

    lines.append(f"סה״כ חוב פתוח: <b>₪{total:,.0f}</b>")
    lines.append(f"מתאמנים עם חוב: <b>{count}</b>")

    if top:
        lines.append(f"")
        lines.append(f"חייבים מעל ₪{threshold} (טופ 5):")
        for d in top:
            lines.append(f"  • {d['name']} — ₪{d['amount']:,.0f}")

    return lines
