# Funnel Intelligence Module — Design Spec

## Problem

The current lead_pipeline module counts leads, trials, and conversions — but raw counts don't tell the owner what to do. A studio owner seeing "179 trials, 103 attended" doesn't know if that's good or bad, or what to fix. They need the system to identify problems, rank them by severity, and tell them what's broken.

## Solution

A new `funnel_intelligence` module that analyzes the lead-to-member funnel for problems, ranks them by impact, and presents the most critical issue first. Two focus areas: **speed to lead** and **funnel dropoff**.

## Data Sources

All from existing Arbox API — no new endpoints needed:

| Report | Fields Used | Purpose |
|--------|------------|---------|
| `leadsInProcessReport` | `created_at`, `updated_at`, `lead_status` | Speed to lead, lead volume |
| `trialClassesReport` | `date`, `check_in`, `class_name`, `source_name` | Trial booking + attendance |
| `convertedLeadReport` | `converted_at`, `name` | Conversion tracking |

## Metrics

### Speed to Lead

Measures how fast the team responds to new leads using `created_at` → `updated_at` as a proxy for first contact.

| Metric | Calculation | Healthy | Warning | Critical |
|--------|------------|---------|---------|----------|
| Median response time | Median of (updated_at - created_at) in hours | < 4h | 4-24h | > 24h |
| Fast response rate | % of leads with response < 4h | > 60% | 30-60% | < 30% |

### Funnel Dropoff

Four conversion rates across the funnel:

| Stage | Calculation | Healthy | Warning | Critical |
|-------|------------|---------|---------|----------|
| Lead → Trial booked | trials_booked / new_leads | > 40% | 20-40% | < 20% |
| Trial booked → Showed | check_in="Yes" / trials_booked | > 70% | 50-70% | < 50% |
| Trial showed → Converted | conversions / check_in="Yes" | > 40% | 25-40% | < 25% |
| Overall: Lead → Member | conversions / new_leads | > 12% | 5-12% | < 5% |

## Priority Ranking

Each metric gets a severity score:
- Critical = 3 points
- Warning = 2 points
- Healthy = 0 points

The report orders issues by score (highest first). If multiple metrics share the same score, the order follows the priority hierarchy:
1. Speed to lead (highest priority)
2. Trial show rate
3. Lead → Trial rate
4. Trial → Conversion rate
5. Overall conversion

If everything is healthy, show a positive summary line.

## Time Window

- **Analysis period:** Rolling 30 days (today minus 30 days → today)
- **Comparison period:** Previous 30 days (today minus 60 days → today minus 30 days)
- Trend arrows (↑↓→) compare current vs previous period

## Output Format

Appears at the TOP of the Telegram summary, before all other module sections.

```
── נקודות פעולה ──

⚠️ זמן תגובה לליד: 28 שעות (חציון)
  רק 15% מהלידים מקבלים מענה תוך 4 שעות
  30 ימים אחרונים: 142 לידים → 21 קיבלו מענה מהיר
  📉 לידים שמקבלים מענה מהיר ממירים פי 3

⚠️ נשירת שיעורי ניסיון: 42% לא הגיעו
  30 ימים אחרונים: 89 נרשמו → 52 הגיעו (37 לא הגיעו)
  📉 הערכה: ~₪7,400 הכנסה אבודה בחודש

✅ המרה מניסיון למנוי: 38% (תקין)
  52 הגיעו → 20 רכשו מנוי
```

Severity indicators:
- 🔴 = Critical (score 3)
- ⚠️ = Warning (score 2)
- ✅ = Healthy (score 0)

## Module Interface

Follows the existing module system pattern:

```python
MODULE_META = {
    "id": "funnel_intelligence",
    "name_he": "נקודות פעולה",
    "description_he": "ניתוח משפך לידים והמלצות לפעולה",
    "default_enabled": True,
    "supports_compare": False,
    "default_params": {},
}

def collect(api_key, week_start, month_start, today, params): -> dict
def format(data, compare_data=None): -> list[str]
```

The `collect` function ignores `week_start`/`month_start` and computes its own 30-day rolling windows.

## Config

Benchmarks stored in `config.json`, overridable per studio:

```json
{
  "funnel_benchmarks": {
    "response_hours_healthy": 4,
    "response_hours_warning": 24,
    "lead_to_trial_healthy": 40,
    "lead_to_trial_warning": 20,
    "trial_show_rate_healthy": 70,
    "trial_show_rate_warning": 50,
    "trial_to_conversion_healthy": 40,
    "trial_to_conversion_warning": 25,
    "overall_conversion_healthy": 12,
    "overall_conversion_warning": 5
  }
}
```

## Relationship to Existing Modules

- **Replaces** `lead_pipeline` module — the old module just counted. This one analyzes.
- The old lead/trial/conversion counts are still shown as context within the funnel analysis.
- **Must appear first** in the Telegram report (before revenue, retention, etc.) — registered first in MODULE_ORDER.

## What's NOT in Scope

- Source ROI analysis (which channels convert best) — phase 2
- Per-salesperson performance breakdown — phase 2
- Lost lead analysis (why people leave) — phase 2
- Revenue impact calculations (₪ lost per problem) — needs pricing data, phase 2
- Name-level drill-downs — secondary, can add via web dashboard later
- Self-benchmarking from historical data — using hardcoded industry benchmarks for now

## Files

| File | Action |
|------|--------|
| `modules/funnel_intelligence.py` | NEW — the intelligence engine |
| `modules/lead_pipeline.py` | DELETE — replaced by funnel_intelligence |
| `modules/__init__.py` | UPDATE — replace lead_pipeline with funnel_intelligence in MODULE_ORDER |
| `config.json` | UPDATE — add funnel_benchmarks section |
| `templates/*.json` | UPDATE — replace lead_pipeline with funnel_intelligence |

## Verification

1. `python send_summary.py --dry-run` — funnel intelligence section appears at top
2. Metrics match manual Arbox filter checks
3. Priority ordering works (worst issue first)
4. Trend arrows show correct direction vs previous 30 days
5. All benchmarks trigger correct severity levels
