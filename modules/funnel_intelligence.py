#!/usr/bin/env python3
"""
Funnel Intelligence module — analyzes the lead-to-member funnel using the local PostgreSQL database.

Computes:
1. Speed to lead (response time)
2. Funnel dropoff rates (lead → trial → show → convert)
3. Time-window conversion analysis (when do conversions happen?)
4. Status breakdown of non-converters (still saveable vs lost)

All queries run against the synced DB — no Arbox API calls at report time.
"""

from datetime import timedelta
from statistics import median
from modules._helpers import fmt

MODULE_META = {
    "id": "funnel_intelligence",
    "name_he": "נקודות פעולה",
    "description_he": "ניתוח משפך לידים והמלצות לפעולה",
    "default_enabled": True,
    "supports_compare": False,
    "default_params": {},
}

DEFAULT_BENCHMARKS = {
    "response_days_healthy": 0,
    "response_days_warning": 2,
    "fast_response_rate_healthy": 60,
    "fast_response_rate_warning": 30,
    "lead_to_trial_healthy": 40,
    "lead_to_trial_warning": 20,
    "trial_show_rate_healthy": 70,
    "trial_show_rate_warning": 50,
    "trial_to_conversion_healthy": 40,
    "trial_to_conversion_warning": 25,
    "overall_conversion_healthy": 12,
    "overall_conversion_warning": 5,
}

PRIORITY_ORDER = [
    "speed_to_lead",
    "trial_show_rate",
    "lead_to_trial",
    "trial_to_conversion",
    "overall_conversion",
]


def _score(value, healthy_threshold, warning_threshold, higher_is_better=True):
    if higher_is_better:
        if value >= healthy_threshold:
            return 0
        if value >= warning_threshold:
            return 2
        return 3
    else:
        if value <= healthy_threshold:
            return 0
        if value <= warning_threshold:
            return 2
        return 3


def _severity_icon(score):
    if score >= 3:
        return "🔴"
    if score >= 2:
        return "⚠️"
    return "✅"


def collect(api_key, week_start, month_start, today, params):
    """Analyze the lead funnel using the local PostgreSQL database."""
    import os, sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from lib.db import get_connection

    today_date = today.date() if hasattr(today, 'date') else today
    current_start = today_date - timedelta(days=30)
    prev_start = today_date - timedelta(days=60)
    prev_end = current_start - timedelta(days=1)

    benchmarks = {**DEFAULT_BENCHMARKS}
    benchmarks.update(params.get("funnel_benchmarks") or {})

    # Determine client_id from config or default
    client_id = params.get("client_id", "a247")
    conn = get_connection(client_id)
    cur = conn.cursor()

    try:
        # ── Speed to Lead ──
        cur.execute("""
            SELECT created_at, updated_at, lead_status
            FROM leads
            WHERE created_at >= %s AND created_at <= %s
        """, (current_start, today_date))
        current_leads_rows = cur.fetchall()

        total_leads_current = len(current_leads_rows)
        response_days_list = []
        same_day_count = 0
        untouched_count = 0

        for created, updated, status in current_leads_rows:
            if status == "Created" and created == updated:
                untouched_count += 1
                continue
            if created and updated:
                days = (updated - created).days
                response_days_list.append(days)
                if days == 0:
                    same_day_count += 1

        touched_leads = len(response_days_list)
        median_response = median(response_days_list) if response_days_list else 0
        fast_rate = round(same_day_count / touched_leads * 100) if touched_leads else 0

        # Previous period lead count
        cur.execute("SELECT COUNT(*) FROM leads WHERE created_at >= %s AND created_at <= %s",
                    (prev_start, prev_end))
        total_leads_prev = cur.fetchone()[0]

        # ── Funnel Rates (current period) ──
        cur.execute("""
            SELECT COUNT(*), SUM(CASE WHEN check_in = 'Yes' THEN 1 ELSE 0 END)
            FROM trials WHERE date >= %s AND date <= %s
        """, (current_start, today_date))
        trials_row = cur.fetchone()
        trials_booked = trials_row[0]
        trials_showed = trials_row[1] or 0

        cur.execute("SELECT COUNT(*) FROM conversions WHERE date >= %s AND date <= %s",
                    (current_start, today_date))
        conversions_current = cur.fetchone()[0]

        # Previous period funnel
        cur.execute("""
            SELECT COUNT(*), SUM(CASE WHEN check_in = 'Yes' THEN 1 ELSE 0 END)
            FROM trials WHERE date >= %s AND date <= %s
        """, (prev_start, prev_end))
        prev_trials_row = cur.fetchone()
        trials_booked_prev = prev_trials_row[0]
        trials_showed_prev = prev_trials_row[1] or 0

        cur.execute("SELECT COUNT(*) FROM conversions WHERE date >= %s AND date <= %s",
                    (prev_start, prev_end))
        conversions_prev = cur.fetchone()[0]

        # ── Time-Window Conversion Analysis ──
        cur.execute("""
            SELECT (c.date - t.date) as days_to_convert
            FROM conversions c
            JOIN trials t ON c.user_id = t.user_id
            WHERE c.date >= %s
        """, (current_start,))
        conversion_days = [row[0] for row in cur.fetchall() if row[0] is not None]

        # Bucket the conversion days
        buckets = {"0-1": 0, "2-3": 0, "4-7": 0, "7+": 0}
        for d in conversion_days:
            if d <= 1:
                buckets["0-1"] += 1
            elif d <= 3:
                buckets["2-3"] += 1
            elif d <= 7:
                buckets["4-7"] += 1
            else:
                buckets["7+"] += 1

        total_conversions_with_trial = len(conversion_days)

        # ── Status Breakdown of Non-Converters ──
        cur.execute("""
            SELECT l.lead_status, COUNT(*) as cnt
            FROM trials t
            JOIN leads l ON t.user_id = l.user_id
            LEFT JOIN conversions c ON t.user_id = c.user_id
            WHERE t.check_in = 'Yes'
              AND t.date >= %s AND t.date <= %s
              AND c.user_id IS NULL
            GROUP BY l.lead_status
            ORDER BY cnt DESC
        """, (current_start, today_date))
        status_breakdown = [{"status": row[0], "count": row[1]} for row in cur.fetchall()]

        # Count: how many trial attendees are still in leads table (saveable)
        still_in_pipeline = sum(s["count"] for s in status_breakdown)

        # Trial attendees who converted (have a match in conversions)
        cur.execute("""
            SELECT COUNT(*)
            FROM trials t
            JOIN conversions c ON t.user_id = c.user_id
            WHERE t.check_in = 'Yes' AND t.date >= %s AND t.date <= %s
        """, (current_start, today_date))
        converted_from_trials = cur.fetchone()[0]

        # Trial attendees NOT in leads AND NOT in conversions = truly lost (removed from system)
        trials_noshow = trials_booked - trials_showed
        truly_lost = trials_showed - still_in_pipeline - converted_from_trials

    finally:
        conn.close()

    # ── Compute rates ──
    lead_to_trial = round(trials_booked / total_leads_current * 100) if total_leads_current else 0
    trial_show_rate = round(trials_showed / trials_booked * 100) if trials_booked else 0
    trial_to_conversion = round(conversions_current / trials_showed * 100) if trials_showed else 0
    overall_conversion = round(conversions_current / total_leads_current * 100) if total_leads_current else 0

    lead_to_trial_prev = round(trials_booked_prev / total_leads_prev * 100) if total_leads_prev else 0
    trial_show_rate_prev = round(trials_showed_prev / trials_booked_prev * 100) if trials_booked_prev else 0
    trial_to_conversion_prev = round(conversions_prev / trials_showed_prev * 100) if trials_showed_prev else 0

    # ── Score and rank issues ──
    issues = []

    speed_score = _score(median_response, benchmarks["response_days_healthy"],
                         benchmarks["response_days_warning"], higher_is_better=False)
    issues.append({
        "id": "speed_to_lead", "score": speed_score,
        "median_days": median_response, "fast_rate": fast_rate,
        "same_day_count": same_day_count, "touched_count": touched_leads,
        "untouched_count": untouched_count, "total_leads": total_leads_current,
    })

    lt_score = _score(lead_to_trial, benchmarks["lead_to_trial_healthy"], benchmarks["lead_to_trial_warning"])
    issues.append({
        "id": "lead_to_trial", "score": lt_score,
        "rate": lead_to_trial, "prev_rate": lead_to_trial_prev,
        "leads": total_leads_current, "trials_booked": trials_booked,
    })

    ts_score = _score(trial_show_rate, benchmarks["trial_show_rate_healthy"], benchmarks["trial_show_rate_warning"])
    issues.append({
        "id": "trial_show_rate", "score": ts_score,
        "rate": trial_show_rate, "prev_rate": trial_show_rate_prev,
        "booked": trials_booked, "showed": trials_showed, "noshow": trials_noshow,
    })

    tc_score = _score(trial_to_conversion, benchmarks["trial_to_conversion_healthy"], benchmarks["trial_to_conversion_warning"])
    issues.append({
        "id": "trial_to_conversion", "score": tc_score,
        "rate": trial_to_conversion, "prev_rate": trial_to_conversion_prev,
        "showed": trials_showed, "converted": conversions_current,
        "status_breakdown": status_breakdown,
        "still_in_pipeline": still_in_pipeline,
        "truly_lost": max(truly_lost, 0),
        "conversion_buckets": buckets,
        "total_with_trial": total_conversions_with_trial,
    })

    oc_score = _score(overall_conversion, benchmarks["overall_conversion_healthy"], benchmarks["overall_conversion_warning"])
    issues.append({
        "id": "overall_conversion", "score": oc_score,
        "rate": overall_conversion, "prev_rate": 0,
        "leads": total_leads_current, "converted": conversions_current,
    })

    # Don't sort by severity — keep funnel order
    # issues are already appended in order: speed, lead_to_trial, trial_show, trial_to_convert, overall

    return {
        "issues": issues,
        "period_days": 30,
        "period_start": current_start.strftime("%d.%m"),
        "period_end": today_date.strftime("%d.%m.%Y"),
        "total_leads": total_leads_current,
        "untouched_count": untouched_count,
        "untouched_pct": round(untouched_count / total_leads_current * 100) if total_leads_current else 0,
    }


RECOMMENDATIONS = {
    "speed_to_lead": "💡 הגדרת התראה אוטומטית לליד חדש יכולה לקצר את זמן התגובה משמעותית",
    "lead_to_trial": "💡 פולואפ טלפוני תוך 24 שעות מכפיל את הסיכוי לקביעת ניסיון",
    "trial_show_rate": "💡 תזכורת וואטסאפ 24 שעות לפני הניסיון מפחיתה אי-הגעה",
    "trial_to_conversion": "💡 שיחת מכירה מיד אחרי הניסיון, כשההתלהבות בשיא",
    "overall_conversion": "💡 שיפור בכל שלב במשפך משפיע ישירות על ההמרה הכוללת",
}


def _fmt_rate(rate, actual_count=None):
    """Format a percentage — show פחות מ-1% when it rounds to 0 but count > 0."""
    if rate == 0 and actual_count and actual_count > 0:
        return "פחות מ-1%"
    return f"{rate}%"


def format(data, compare_data=None):
    """Format funnel intelligence as Hebrew action items."""
    RLM = "\u200f"
    lines = []
    issues = data.get("issues", [])

    if not issues:
        return lines

    # Header with date range
    period_start = data.get("period_start", "")
    period_end = data.get("period_end", "")
    lines.append(f"{RLM}<b>── משפך לידים ──</b>")
    lines.append(f"{RLM}30 ימים אחרונים ({period_start} - {period_end})")
    lines.append("")

    # ── Untouched leads (always first) ──
    ut_count = data.get("untouched_count", 0)
    ut_pct = data.get("untouched_pct", 0)
    total = data.get("total_leads", 0)
    if ut_count > 0:
        ut_icon = "🔴" if ut_pct > 20 else "⚠️" if ut_pct > 10 else "✅"
        lines.append(f"{RLM}{ut_icon} <b>{ut_count} לידים מחכים לטיפול</b> ({ut_pct}% מכלל הלידים)")
        if ut_icon == "🔴":
            lines.append(f"{RLM}💡 לידים שלא מטופלים תוך 48 שעות כמעט לא ממירים")
        lines.append("")

    # ── Funnel stages in order ──
    # Build a dict for easy lookup
    issues_dict = {i["id"]: i for i in issues}

    # 1. Speed to lead
    issue = issues_dict.get("speed_to_lead")
    if issue:
        icon = _severity_icon(issue["score"])
        md = issue["median_days"]
        sc = issue["same_day_count"]
        tl = issue["total_leads"]
        all_leads_fast_rate = round(sc / tl * 100) if tl else 0

        if md == 0:
            lines.append(f"{RLM}{icon} רוב הלידים מקבלים מענה <b>באותו יום</b>")
        elif md == 1:
            lines.append(f"{RLM}{icon} רוב הלידים מקבלים מענה <b>תוך יום</b>")
        else:
            lines.append(f"{RLM}{icon} רוב הלידים מקבלים מענה <b>תוך {md} ימים</b>")

        lines.append(f"{RLM}  {all_leads_fast_rate}% מכל הלידים קיבלו מענה באותו יום ({sc} מתוך {tl})")
        if issue["score"] >= 3:
            lines.append(f"{RLM}{RECOMMENDATIONS['speed_to_lead']}")
        lines.append("")

    # 2. Lead to trial
    issue = issues_dict.get("lead_to_trial")
    if issue:
        icon = _severity_icon(issue["score"])
        rate = issue["rate"]
        trend = _trend_text(rate, issue["prev_rate"])

        lines.append(f"{RLM}{icon} ליד לניסיון: <b>{rate}%</b>{trend}")
        lines.append(f"{RLM}  מתוך {issue['leads']} לידים, {issue['trials_booked']} נרשמו לניסיון")
        if issue["score"] >= 3:
            lines.append(f"{RLM}{RECOMMENDATIONS['lead_to_trial']}")
        lines.append("")

    # 3. Trial show rate
    issue = issues_dict.get("trial_show_rate")
    if issue:
        icon = _severity_icon(issue["score"])
        rate = issue["rate"]
        trend = _trend_text(rate, issue["prev_rate"])

        lines.append(f"{RLM}{icon} הגעה לניסיון: <b>{rate}%</b>{trend}")
        lines.append(f"{RLM}  מתוך {issue['booked']} שנרשמו, {issue['showed']} הגיעו ({issue['noshow']} לא הגיעו)")
        if issue["score"] >= 3:
            lines.append(f"{RLM}{RECOMMENDATIONS['trial_show_rate']}")
        lines.append("")

    # 4. Trial to conversion
    issue = issues_dict.get("trial_to_conversion")
    if issue:
        icon = _severity_icon(issue["score"])
        rate = issue["rate"]
        converted = issue["converted"]
        rate_str = _fmt_rate(rate, converted)
        trend = _trend_text(rate, issue["prev_rate"])

        lines.append(f"{RLM}{icon} ניסיון למנוי: <b>{rate_str}</b>{trend}")

        still = issue.get("still_in_pipeline", 0)
        lost = issue.get("truly_lost", 0)
        lines.append(f"{RLM}  מתוך {issue['showed']} שהגיעו לניסיון:")
        lines.append(f"{RLM}  • {converted} רכשו מנוי")
        if still > 0:
            lines.append(f"{RLM}  • {still} עדיין בטיפול")
        if lost > 0:
            lines.append(f"{RLM}  • {lost} סומנו כפניות אבודות")

        # Time-window — only show when >= 10 conversions
        total_with = issue.get("total_with_trial", 0)
        if total_with >= 10:
            buckets = issue.get("conversion_buckets", {})
            lines.append(f"{RLM}")
            lines.append(f"{RLM}  <b>חלון המרה (ימים מניסיון לרכישה):</b>")
            cum = 0
            for label, count in buckets.items():
                cum += count
                pct = round(cum / total_with * 100)
                he_label = {"0-1": "תוך יום", "2-3": "תוך 3 ימים",
                            "4-7": "תוך שבוע", "7+": "אחרי שבוע"}[label]
                lines.append(f"{RLM}  • {he_label}: {pct}% ({cum} מתוך {total_with})")

        if issue["score"] >= 3:
            lines.append(f"{RLM}{RECOMMENDATIONS['trial_to_conversion']}")
        lines.append("")

    # 5. Overall conversion
    issue = issues_dict.get("overall_conversion")
    if issue:
        icon = _severity_icon(issue["score"])
        rate = issue["rate"]
        converted = issue["converted"]
        rate_str = _fmt_rate(rate, converted)

        lines.append(f"{RLM}{icon} המרה כוללת: <b>{rate_str}</b>")
        lines.append(f"{RLM}  מתוך {issue['leads']} לידים, {converted} הפכו למנויים")
        if issue["score"] >= 3:
            lines.append(f"{RLM}{RECOMMENDATIONS['overall_conversion']}")

    # Remove trailing blanks
    while lines and lines[-1] == "":
        lines.pop()

    return lines


def _trend_text(current, previous, min_delta=15):
    """Show comparison only when change is dramatic (>15pp), with context."""
    if not previous:
        return ""
    delta = current - previous
    if abs(delta) < min_delta:
        return ""
    if delta > 0:
        return f" (עלייה מ-{previous}% בחודש שעבר)"
    else:
        return f" (ירידה מ-{previous}% בחודש שעבר)"
