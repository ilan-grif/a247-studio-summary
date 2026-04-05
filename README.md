# a247 Studio Summary

Configurable studio reporting system that pulls metrics from Arbox and delivers formatted Hebrew summaries via Telegram.

## Features

- **11 metric modules** — leads, revenue, retention, operations, debt, cancellations, renewals, birthdays, and more
- **3 studio templates** — martial arts, yoga/pilates, general fitness
- **Configurable** — toggle modules on/off, adjust thresholds, compare periods
- **Web dashboard** — visual configuration UI
- **Telegram delivery** — formatted Hebrew reports

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your Arbox API key and Telegram bot credentials

# Run a dry-run (prints report without sending)
python send_summary.py --dry-run

# Send to Telegram
python send_summary.py

# Start the configuration dashboard
python dashboard_server.py
# Open http://localhost:5020
```

## Configuration

Edit `config.json` to set your template and module overrides:

```json
{
  "template": "martial_arts",
  "module_overrides": {
    "retention": { "ghost_days": 21 },
    "debt": { "enabled": false }
  }
}
```

Or use the web dashboard at `http://localhost:5020`.

## Templates

| Template | Focus |
|----------|-------|
| `martial_arts` | High trial volume, class structure, debt tracking |
| `yoga_pilates` | Community-focused, birthdays, seasonal freezes |
| `general_fitness` | Broad default covering most use cases |

## Modules

| Module | Description | Default |
|--------|-------------|---------|
| `lead_pipeline` | New leads, trials, conversions | On |
| `revenue` | Sales count + revenue | On |
| `expiring` | Memberships about to lapse | On |
| `retention` | Ghost members, cancellations | On |
| `operations` | Class fill rates | On |
| `debt` | Outstanding debt tracking | Off |
| `late_cancellations` | Same-day cancellations | Off |
| `renewals_forecast` | Upcoming renewals | On |
| `birthdays` | Member birthdays this week | Off |
| `members_on_hold` | Frozen memberships | Off |
| `staff` | Instructor attendance | Off |
