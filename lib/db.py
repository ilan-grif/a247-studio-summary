#!/usr/bin/env python3
"""
Database connection and schema management for multi-tenant studio analytics.

Each client gets their own PostgreSQL schema within the studio_analytics database.
Schema-per-client provides clean isolation and easy migration (pg_dump per schema).

Usage:
    from lib.db import get_connection, create_client_schema, register_client

    # Register a new client
    register_client("a247", arbox_api_key="xxx", config={...})

    # Create schema + tables for a client
    create_client_schema("a247")

    # Get a connection scoped to a client's schema
    conn = get_connection("a247")
    cur = conn.cursor()
    cur.execute("SELECT * FROM leads WHERE created_at >= %s", (date,))
"""

import os
import json
import logging
import psycopg2
from psycopg2.extras import execute_values

logger = logging.getLogger(__name__)


def _get_db_url():
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL not set in .env")
    return url


def get_connection(client_id=None):
    """Get a PostgreSQL connection, optionally scoped to a client schema."""
    conn = psycopg2.connect(_get_db_url())
    conn.autocommit = False
    if client_id:
        schema = _schema_name(client_id)
        cur = conn.cursor()
        cur.execute(f"SET search_path TO {schema}, public")
        cur.close()
    return conn


def _schema_name(client_id):
    """Sanitize client_id into a valid schema name."""
    return f"client_{client_id.replace('-', '_')}"


# ── Schema Management ────────────────────────────────────────────────────

TABLES_SQL = """
CREATE TABLE IF NOT EXISTS leads (
    user_id         INTEGER PRIMARY KEY,
    name            TEXT,
    phone           TEXT,
    lead_status     TEXT,
    lead_source     TEXT,
    campaign        TEXT,
    lead_owner      TEXT,
    lead_owner_id   INTEGER,
    created_at      DATE,
    updated_at      DATE,
    location_name   TEXT,
    synced_at       TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS trials (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER,
    date            DATE,
    class_name      TEXT,
    check_in        TEXT,
    staff_member    TEXT,
    source_name     TEXT,
    booked_by       TEXT,
    synced_at       TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, date, class_name)
);

CREATE TABLE IF NOT EXISTS conversions (
    lead_id         INTEGER PRIMARY KEY,
    user_id         INTEGER,
    converted_at    DATE,
    converted_by    TEXT,
    converted_by_id INTEGER,
    membership_type TEXT,
    lead_source     TEXT,
    synced_at       TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sales (
    sale_id         INTEGER PRIMARY KEY,
    user_id         INTEGER,
    date            DATE,
    price           NUMERIC,
    paid            NUMERIC,
    debt            NUMERIC,
    action          TEXT,
    item_name       TEXT,
    status          TEXT,
    department_name TEXT,
    start_date      DATE,
    end_date        DATE,
    synced_at       TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sync_log (
    id              SERIAL PRIMARY KEY,
    report_name     TEXT,
    started_at      TIMESTAMP,
    completed_at    TIMESTAMP,
    records_synced  INTEGER,
    status          TEXT
);

CREATE INDEX IF NOT EXISTS idx_leads_created ON leads(created_at);
CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(lead_status);
CREATE INDEX IF NOT EXISTS idx_trials_date ON trials(date);
CREATE INDEX IF NOT EXISTS idx_trials_user ON trials(user_id);
CREATE INDEX IF NOT EXISTS idx_conversions_date ON conversions(converted_at);
CREATE INDEX IF NOT EXISTS idx_conversions_user ON conversions(user_id);
CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(date);
CREATE INDEX IF NOT EXISTS idx_sales_user ON sales(user_id);
"""

PLATFORM_SQL = """
CREATE SCHEMA IF NOT EXISTS platform;

CREATE TABLE IF NOT EXISTS platform.clients (
    client_id       TEXT PRIMARY KEY,
    client_name     TEXT,
    arbox_api_key   TEXT,
    template        TEXT DEFAULT 'general_fitness',
    config          JSONB DEFAULT '{}',
    sync_schedule   TEXT DEFAULT '0 6,18 * * *',
    created_at      TIMESTAMP DEFAULT NOW(),
    last_sync_at    TIMESTAMP
);
"""


def create_platform_tables():
    """Create the shared platform schema and clients table."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(PLATFORM_SQL)
        conn.commit()
        logger.info("Platform tables created")
    finally:
        conn.close()


def create_client_schema(client_id):
    """Create schema and all tables for a client."""
    schema = _schema_name(client_id)
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        cur.execute(f"SET search_path TO {schema}")
        cur.execute(TABLES_SQL)
        conn.commit()
        logger.info(f"Schema '{schema}' created with all tables")
    finally:
        conn.close()


def register_client(client_id, client_name="", arbox_api_key="", template="general_fitness", config=None):
    """Register a client in the platform table and create their schema."""
    create_platform_tables()
    create_client_schema(client_id)

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO platform.clients (client_id, client_name, arbox_api_key, template, config)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (client_id) DO UPDATE SET
                client_name = EXCLUDED.client_name,
                arbox_api_key = EXCLUDED.arbox_api_key,
                template = EXCLUDED.template,
                config = EXCLUDED.config
        """, (client_id, client_name, arbox_api_key, template, json.dumps(config or {})))
        conn.commit()
        logger.info(f"Client '{client_id}' registered")
    finally:
        conn.close()


def get_client(client_id):
    """Get client config from platform table."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT client_id, client_name, arbox_api_key, template, config FROM platform.clients WHERE client_id = %s", (client_id,))
        row = cur.fetchone()
        if not row:
            return None
        return {
            "client_id": row[0],
            "client_name": row[1],
            "arbox_api_key": row[2],
            "template": row[3],
            "config": row[4] if isinstance(row[4], dict) else json.loads(row[4] or "{}"),
        }
    finally:
        conn.close()


def get_all_clients():
    """Get all registered clients."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT client_id, client_name, arbox_api_key, template, config, last_sync_at FROM platform.clients ORDER BY client_id")
        rows = cur.fetchall()
        return [{
            "client_id": r[0], "client_name": r[1], "arbox_api_key": r[2],
            "template": r[3], "config": r[4] if isinstance(r[4], dict) else json.loads(r[4] or "{}"),
            "last_sync_at": r[5],
        } for r in rows]
    finally:
        conn.close()


# ── Upsert Helpers ───────────────────────────────────────────────────────

def upsert_leads(conn, leads_data):
    """Upsert leads into the client's leads table."""
    if not leads_data:
        return 0
    cur = conn.cursor()
    values = []
    for l in leads_data:
        values.append((
            l.get("user_id"),
            l.get("name", ""),
            l.get("phone", ""),
            l.get("lead_status", ""),
            l.get("lead_source", ""),
            l.get("campaign", ""),
            l.get("lead_owner", ""),
            l.get("lead_owner_id"),
            l.get("created_at"),
            l.get("updated_at"),
            l.get("location_name", ""),
        ))
    execute_values(cur, """
        INSERT INTO leads (user_id, name, phone, lead_status, lead_source, campaign,
                          lead_owner, lead_owner_id, created_at, updated_at, location_name, synced_at)
        VALUES %s
        ON CONFLICT (user_id) DO UPDATE SET
            name = EXCLUDED.name,
            phone = EXCLUDED.phone,
            lead_status = EXCLUDED.lead_status,
            lead_source = EXCLUDED.lead_source,
            campaign = EXCLUDED.campaign,
            lead_owner = EXCLUDED.lead_owner,
            lead_owner_id = EXCLUDED.lead_owner_id,
            updated_at = EXCLUDED.updated_at,
            location_name = EXCLUDED.location_name,
            synced_at = NOW()
    """, values, template="(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())")
    return len(values)


def upsert_trials(conn, trials_data):
    """Upsert trials into the client's trials table."""
    if not trials_data:
        return 0
    cur = conn.cursor()
    values = []
    for t in trials_data:
        values.append((
            t.get("user_id"),
            t.get("date"),
            t.get("class_name", ""),
            t.get("check_in", "No"),
            t.get("staff_member", ""),
            t.get("source_name", ""),
            t.get("booked_by", ""),
        ))
    execute_values(cur, """
        INSERT INTO trials (user_id, date, class_name, check_in, staff_member, source_name, booked_by, synced_at)
        VALUES %s
        ON CONFLICT (user_id, date, class_name) DO UPDATE SET
            check_in = EXCLUDED.check_in,
            staff_member = EXCLUDED.staff_member,
            source_name = EXCLUDED.source_name,
            booked_by = EXCLUDED.booked_by,
            synced_at = NOW()
    """, values, template="(%s, %s, %s, %s, %s, %s, %s, NOW())")
    return len(values)


def upsert_conversions(conn, conversions_data):
    """Upsert conversions into the client's conversions table."""
    if not conversions_data:
        return 0
    cur = conn.cursor()
    values = []
    for c in conversions_data:
        values.append((
            c.get("lead_id"),
            c.get("user_id"),
            c.get("converted_at"),
            c.get("converted_by", ""),
            c.get("converted_by_id"),
            c.get("membership_type_name", ""),
            c.get("lead_source", ""),
        ))
    execute_values(cur, """
        INSERT INTO conversions (lead_id, user_id, converted_at, converted_by, converted_by_id, membership_type, lead_source, synced_at)
        VALUES %s
        ON CONFLICT (lead_id) DO UPDATE SET
            converted_at = EXCLUDED.converted_at,
            converted_by = EXCLUDED.converted_by,
            membership_type = EXCLUDED.membership_type,
            synced_at = NOW()
    """, values, template="(%s, %s, %s, %s, %s, %s, %s, NOW())")
    return len(values)


def upsert_sales(conn, sales_data):
    """Upsert sales into the client's sales table."""
    if not sales_data:
        return 0
    cur = conn.cursor()
    values = []
    for s in sales_data:
        values.append((
            s.get("sale_id"),
            s.get("user_id"),
            s.get("date"),
            float(s.get("price") or 0),
            float(s.get("paid") or 0),
            float(s.get("debt") or 0),
            s.get("action", ""),
            s.get("item_name", ""),
            s.get("status", ""),
            s.get("department_name", ""),
            s.get("start_date"),
            s.get("end_date"),
        ))
    execute_values(cur, """
        INSERT INTO sales (sale_id, user_id, date, price, paid, debt, action, item_name,
                          status, department_name, start_date, end_date, synced_at)
        VALUES %s
        ON CONFLICT (sale_id) DO UPDATE SET
            price = EXCLUDED.price,
            paid = EXCLUDED.paid,
            debt = EXCLUDED.debt,
            action = EXCLUDED.action,
            status = EXCLUDED.status,
            synced_at = NOW()
    """, values, template="(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())")
    return len(values)
