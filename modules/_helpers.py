#!/usr/bin/env python3
"""Shared helpers for studio summary modules."""

import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from lib.arbox_api import get_leads, get_report, get_bookings

logger = logging.getLogger(__name__)


def fmt(dt):
    """Format datetime as YYYY-MM-DD string."""
    return dt.strftime("%Y-%m-%d")


def week_start(dt):
    """Sunday of the current week (Israel standard)."""
    days_since_sunday = (dt.weekday() + 1) % 7
    return (dt - timedelta(days=days_since_sunday)).replace(hour=0, minute=0, second=0, microsecond=0)


def month_start(dt):
    return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def safe_list(result):
    """Extract list from Arbox API response."""
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        if result.get("statusCode", 200) >= 400:
            logger.warning(f"API error: {result.get('error', 'unknown')}")
            return []
        data = result.get("data", [])
        if data is None:
            return []
        return data if isinstance(data, list) else [data]
    return []


def get_paginated(api_key, report_name, max_pages=100, **params):
    """Fetch all pages of a paginated Arbox report."""
    all_data = []
    page = 1
    while page <= max_pages:
        result = get_report(api_key, report_name, page=page, **params)
        batch = safe_list(result)
        all_data.extend(batch)
        extra = result.get("extra", {}) if isinstance(result, dict) else {}
        pagination = extra.get("pagination", extra)
        total_pages = pagination.get("total_pages", 1)
        if page >= total_pages or not batch:
            break
        page += 1
    return all_data


def date_he(date_str):
    """Convert YYYY-MM-DD to DD.MM format."""
    if not date_str:
        return ""
    parts = date_str.split("-")
    if len(parts) == 3:
        return f"{parts[2]}.{parts[1]}"
    return date_str


def date_full_he(date_str):
    """Convert YYYY-MM-DD to DD.MM.YYYY format."""
    if not date_str:
        return ""
    parts = date_str.split("-")
    if len(parts) == 3:
        return f"{parts[2]}.{parts[1]}.{parts[0]}"
    return date_str
