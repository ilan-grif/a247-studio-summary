#!/usr/bin/env python3
"""
Send studio summary — main entry point.
Collects data from Arbox using module system, formats as Hebrew report, sends via Telegram.

Usage:
    python send_summary.py
    python send_summary.py --dry-run
    python send_summary.py --template yoga_pilates
"""

import os
import sys
import json
import argparse
import logging
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

from data_collector import collect_studio_data
from report_formatter import format_telegram_message
from lib.telegram_notify import send_message


def load_config(template_override=None):
    config_path = REPO_ROOT / "config.json"
    with open(config_path) as f:
        config = json.load(f)
    if template_override:
        config["template"] = template_override
    return config


def main():
    parser = argparse.ArgumentParser(description="Send studio summary to Telegram")
    parser.add_argument("--dry-run", action="store_true", help="Print message without sending")
    parser.add_argument("--template", help="Override template (e.g. yoga_pilates, martial_arts)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")

    config = load_config(args.template)

    api_key = os.getenv("A247_ARBOX_API_KEY")
    if not api_key:
        print("ERROR: A247_ARBOX_API_KEY not set in .env")
        sys.exit(1)

    print(f"Collecting studio data (template: {config.get('template', 'default')})...")
    data = collect_studio_data(api_key, config)

    print("Formatting report...")
    message = format_telegram_message(data, config)

    if args.dry_run:
        print("\n--- DRY RUN (would send to Telegram) ---\n")
        print(message)
        print("\n--- Raw data ---\n")
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print("Sending to Telegram...")
        result = send_message(message)
        if result:
            print(f"Sent! Message ID: {result.get('message_id', 'unknown')}")
        else:
            print("ERROR: Failed to send message")
            sys.exit(1)


if __name__ == "__main__":
    main()
