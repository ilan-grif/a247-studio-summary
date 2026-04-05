#!/usr/bin/env python3
"""Lead pipeline module — new leads, trials, and conversions."""

from modules._helpers import fmt, safe_list, get_paginated

MODULE_META = {
    "id": "lead_pipeline",
    "name_he": "לידים ושיעורי ניסיון",
    "description_he": "לידים חדשים, שיעורי ניסיון, נוכחות והמרות למנוי",
    "default_enabled": True,
    "supports_compare": True,
    "default_params": {},
}


def collect(api_key, week_start, month_start, today, params):
    month_str = fmt(month_start)
    week_str = fmt(week_start)
    today_str = fmt(today)

    # Leads — fetch ALL pages of leadsInProcessReport (200/page, ~13s for 4500+ leads)
    # Arbox returns leads in random order, so we must scan everything
    all_leads = get_paginated(api_key, "leadsInProcessReport")
    new_week = new_month = 0
    for lead in all_leads:
        created = (lead.get("created_at") or "")[:10]
        if created >= month_str:
            new_month += 1
        if created >= week_str:
            new_week += 1

    # Trials
    trials = get_paginated(api_key, "trialClassesReport",
                           fromDate=month_str, toDate=today_str)
    booked_week = attended_week = 0
    booked_month = attended_month = 0
    for t in trials:
        trial_date = t.get("date", "")
        checked_in = t.get("check_in") == "Yes"
        if trial_date >= month_str:
            booked_month += 1
            if checked_in:
                attended_month += 1
        if trial_date >= week_str:
            booked_week += 1
            if checked_in:
                attended_week += 1

    # Conversions
    conversions = get_paginated(api_key, "convertedLeadReport",
                                fromDate=month_str, toDate=today_str)
    conv_week = sum(1 for c in conversions if c.get("converted_at", "") >= week_str)

    return {
        "new_leads_week": new_week,
        "new_leads_month": new_month,
        "booked_week": booked_week,
        "attended_week": attended_week,
        "noshow_week": booked_week - attended_week,
        "booked_month": booked_month,
        "attended_month": attended_month,
        "noshow_month": booked_month - attended_month,
        "attendance_rate_week": round(attended_week / booked_week * 100) if booked_week else 0,
        "attendance_rate_month": round(attended_month / booked_month * 100) if booked_month else 0,
        "converted_week": conv_week,
        "converted_month": len(conversions),
    }


def format(data, compare_data=None):
    lines = []
    lines.append("<b>── לידים ושיעורי ניסיון ──</b>")

    lw = data.get("new_leads_week", 0)
    lm = data.get("new_leads_month", 0)
    lead_line = f"לידים חדשים: <b>{lw}</b> (השבוע) | <b>{lm}</b> (החודש)"
    if compare_data:
        prev_lw = compare_data.get("new_leads_week", 0)
        prev_lm = compare_data.get("new_leads_month", 0)
        if prev_lw:
            arrow = "↑" if lw > prev_lw else "↓" if lw < prev_lw else "→"
            lead_line += f" {arrow} מ-{prev_lw}"
    lines.append(lead_line)

    bw = data.get("booked_week", 0)
    aw = data.get("attended_week", 0)
    bm = data.get("booked_month", 0)
    am = data.get("attended_month", 0)
    rw = data.get("attendance_rate_week", 0)
    rm = data.get("attendance_rate_month", 0)

    lines.append(f"שיעורי ניסיון השבוע: {bw} נרשמו → {aw} הגיעו ({rw}%)")
    lines.append(f"שיעורי ניסיון החודש: {bm} נרשמו → {am} הגיעו ({rm}%)")

    cw = data.get("converted_week", 0)
    cm = data.get("converted_month", 0)
    lines.append(f"המרה למנוי: <b>{cw}</b> (השבוע) | <b>{cm}</b> (החודש)")

    return lines
