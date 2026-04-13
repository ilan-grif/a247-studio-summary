#!/usr/bin/env python3
"""
Studio data collector — modular system that pulls metrics from Arbox API.

Resolves config (template + overrides), runs enabled modules, returns structured dict.

CLI:
    python data_collector.py
"""

import os
import sys
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

from modules import resolve_config, get_enabled_modules
from modules._helpers import fmt, week_start, month_start

logger = logging.getLogger(__name__)


def _today():
    return datetime.now()


def _prev_week(ws):
    """Previous week: Sunday-Saturday before current week."""
    prev_end = ws - timedelta(days=1)
    prev_start = prev_end - timedelta(days=6)
    return prev_start, prev_end


def _prev_month(ms):
    """Previous month: 1st to last day of previous month."""
    prev_end = ms - timedelta(days=1)
    prev_start = prev_end.replace(day=1)
    return prev_start, prev_end


def collect_studio_data(api_key, config):
    """Pull all studio metrics from Arbox using the module system.

    Args:
        api_key: Arbox API key
        config: dict with 'template' and optional 'module_overrides'

    Returns:
        dict with module results keyed by module_id
    """
    today = _today()
    ws = week_start(today)
    ms = month_start(today)

    logger.info(f"Collecting studio data: week={fmt(ws)}, month={fmt(ms)}")

    resolved = resolve_config(config)
    enabled = get_enabled_modules(resolved)

    data = {
        "generated_at": today.isoformat(),
        "period": {
            "week_start": fmt(ws),
            "month_start": fmt(ms),
            "today": fmt(today),
        },
    }

    for mod, mod_config in enabled:
        module_id = mod.MODULE_META["id"]
        # Inject top-level config sections into module params
        if "funnel_benchmarks" in config:
            mod_config["funnel_benchmarks"] = config["funnel_benchmarks"]
        if "client_id" in config:
            mod_config["client_id"] = config["client_id"]
        try:
            # Collect current period
            result = mod.collect(api_key, ws, ms, today, mod_config)
            data[module_id] = result

            # Collect comparison period if enabled
            if mod_config.get("compare") and mod.MODULE_META.get("supports_compare"):
                prev_ws, prev_we = _prev_week(ws)
                prev_ms, prev_me = _prev_month(ms)
                compare_result = mod.collect(api_key, prev_ws, prev_ms, prev_me, mod_config)
                data[f"{module_id}_compare"] = compare_result

            logger.info(f"  ✓ {module_id}")
        except Exception as e:
            logger.error(f"  ✗ {module_id}: {e}")
            data[module_id] = {"error": str(e)}

    return data


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / ".env")
    logging.basicConfig(level=logging.INFO)

    api_key = os.getenv("A247_ARBOX_API_KEY")
    if not api_key:
        print("A247_ARBOX_API_KEY not set in .env")
        sys.exit(1)

    config_path = REPO_ROOT / "config.json"
    with open(config_path) as f:
        config = json.load(f)

    data = collect_studio_data(api_key, config)
    print(json.dumps(data, indent=2, ensure_ascii=False))
