#!/usr/bin/env python3
"""
Sync engine — pulls data from Arbox API and upserts into PostgreSQL.

Runs per-client. Pulls all pages of each report and upserts into the client's schema.

Usage:
    python sync_engine.py                    # sync all registered clients
    python sync_engine.py --client a247      # sync one client
    python sync_engine.py --register a247    # register a new client (uses A247_ARBOX_API_KEY from .env)
"""

import os
import sys
import argparse
import logging
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv
load_dotenv(REPO_ROOT / ".env")

from lib.db import (
    get_connection, register_client, get_client, get_all_clients,
    upsert_leads, upsert_trials, upsert_conversions, upsert_sales,
)
from lib.arbox_api import get_report, get_leads

logger = logging.getLogger(__name__)


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


def sync_client(client_id, api_key=None):
    """Sync all Arbox data for a single client into their DB schema."""
    if not api_key:
        client = get_client(client_id)
        if not client:
            logger.error(f"Client '{client_id}' not registered")
            return False
        api_key = client["arbox_api_key"]

    logger.info(f"Syncing client '{client_id}'...")
    conn = get_connection(client_id)
    started = datetime.now()

    try:
        # Sync leads
        logger.info("  Pulling leads...")
        leads = get_paginated(api_key, "leadsInProcessReport")
        n_leads = upsert_leads(conn, leads)
        logger.info(f"  ✓ {n_leads} leads synced")

        # Sync date-filtered reports in 30-day chunks (Arbox max: 31 days per request)
        from datetime import timedelta
        today = datetime.now()
        chunks = []
        for i in range(3):  # 3 chunks = ~90 days
            chunk_end = today - timedelta(days=i * 30)
            chunk_start = today - timedelta(days=(i + 1) * 30)
            chunks.append((chunk_start.strftime("%Y-%m-%d"), chunk_end.strftime("%Y-%m-%d")))

        # Sync trials
        logger.info("  Pulling trials...")
        n_trials = 0
        for from_d, to_d in chunks:
            trials = get_paginated(api_key, "trialClassesReport", fromDate=from_d, toDate=to_d)
            n_trials += upsert_trials(conn, trials)
        logger.info(f"  ✓ {n_trials} trials synced")

        # Sync conversions
        logger.info("  Pulling conversions...")
        n_conv = 0
        for from_d, to_d in chunks:
            conversions = get_paginated(api_key, "convertedLeadReport", fromDate=from_d, toDate=to_d)
            n_conv += upsert_conversions(conn, conversions)
        logger.info(f"  ✓ {n_conv} conversions synced")

        # Sync sales
        logger.info("  Pulling sales...")
        n_sales = 0
        for from_d, to_d in chunks:
            sales = get_paginated(api_key, "salesReport", fromDate=from_d, toDate=to_d)
            n_sales += upsert_sales(conn, sales)
        logger.info(f"  ✓ {n_sales} sales synced")

        # Log sync
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO sync_log (report_name, started_at, completed_at, records_synced, status)
            VALUES ('full_sync', %s, NOW(), %s, 'success')
        """, (started, n_leads + n_trials + n_conv + n_sales))

        conn.commit()

        # Update platform last_sync_at
        platform_conn = get_connection()
        platform_cur = platform_conn.cursor()
        platform_cur.execute("UPDATE platform.clients SET last_sync_at = NOW() WHERE client_id = %s", (client_id,))
        platform_conn.commit()
        platform_conn.close()

        elapsed = (datetime.now() - started).total_seconds()
        logger.info(f"  Done in {elapsed:.1f}s — {n_leads + n_trials + n_conv + n_sales} total records")
        return True

    except Exception as e:
        conn.rollback()
        logger.error(f"  Sync failed: {e}")

        # Log failure
        try:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO sync_log (report_name, started_at, completed_at, records_synced, status)
                VALUES ('full_sync', %s, NOW(), 0, %s)
            """, (started, f"failed: {str(e)[:200]}"))
            conn.commit()
        except Exception:
            pass

        return False
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Sync Arbox data to PostgreSQL")
    parser.add_argument("--client", help="Sync a specific client (default: all)")
    parser.add_argument("--register", help="Register a new client")
    parser.add_argument("--list", action="store_true", help="List registered clients")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    if args.list:
        clients = get_all_clients()
        if not clients:
            print("No clients registered")
        for c in clients:
            last = c["last_sync_at"] or "never"
            print(f"  {c['client_id']}: {c['client_name']} (last sync: {last})")
        return

    if args.register:
        client_id = args.register
        # Use env var for API key based on client_id pattern
        api_key_var = f"{client_id.upper().replace('-', '_')}_ARBOX_API_KEY"
        api_key = os.getenv(api_key_var) or os.getenv("A247_ARBOX_API_KEY")
        if not api_key:
            print(f"ERROR: Set {api_key_var} in .env")
            sys.exit(1)

        register_client(client_id, client_name=client_id, arbox_api_key=api_key)
        print(f"Client '{client_id}' registered. Run: python sync_engine.py --client {client_id}")
        return

    if args.client:
        success = sync_client(args.client)
        sys.exit(0 if success else 1)
    else:
        clients = get_all_clients()
        if not clients:
            print("No clients registered. Use: python sync_engine.py --register <client_id>")
            sys.exit(1)

        for client in clients:
            sync_client(client["client_id"], client["arbox_api_key"])


if __name__ == "__main__":
    main()
