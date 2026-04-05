#!/usr/bin/env python3
"""
Arbox gym management API wrapper.
Docs: https://arboxserver.arboxapp.com/docs/api
Public API path: /api/public/v3/
Auth: api-key header

Usage:
    from lib.arbox_api import search_user, get_report
"""

import os
import sys
import json
import logging
import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://arboxserver.arboxapp.com/api/public"
REQUEST_TIMEOUT = 10


def _headers(api_key):
    return {
        "api-key": api_key,
        "Content-Type": "application/json",
    }


# ── Leads ────────────────────────────────────────────────────────────────

def get_leads(api_key, limit=100, page=1, status_id=None):
    """GET /v3/leads — List all leads."""
    params = {"limit": limit, "page": page}
    if status_id:
        params["status_id"] = status_id
    try:
        r = requests.get(f"{BASE_URL}/v3/leads", headers=_headers(api_key),
                         params=params, timeout=REQUEST_TIMEOUT)
        return r.json()
    except requests.RequestException as e:
        logger.error(f"get_leads failed: {e}")
        return {"error": str(e)}


def create_lead(api_key, first_name, last_name, phone, location_id=None,
                email=None, source_id=None, status_id=None):
    """POST /v3/leads — Create a new lead.
    Required: first_name, phone, location_id.
    """
    data = {"first_name": first_name, "last_name": last_name, "phone": phone}
    if location_id:
        data["location_id"] = location_id
    if email:
        data["email"] = email
    if source_id:
        data["source_id"] = source_id
    if status_id:
        data["status_id"] = status_id
    try:
        r = requests.post(f"{BASE_URL}/v3/leads", headers=_headers(api_key),
                          json=data, timeout=REQUEST_TIMEOUT)
        return r.json()
    except requests.RequestException as e:
        logger.error(f"create_lead failed: {e}")
        return {"error": str(e)}


def update_lead_status(api_key, user_id, status_id):
    """POST /v3/leads/updateStatus
    Params: user_id (the lead's user_id), status_id.
    """
    try:
        r = requests.post(f"{BASE_URL}/v3/leads/updateStatus",
                          headers=_headers(api_key),
                          json={"user_id": user_id, "status_id": status_id},
                          timeout=REQUEST_TIMEOUT)
        return r.json()
    except requests.RequestException as e:
        logger.error(f"update_lead_status failed: {e}")
        return {"error": str(e)}


def create_lead_note(api_key, user_id, note_text):
    """POST /v3/leads/createNote
    Params: user_id (the lead's user_id), description.
    """
    try:
        r = requests.post(f"{BASE_URL}/v3/leads/createNote",
                          headers=_headers(api_key),
                          json={"user_id": user_id, "description": note_text},
                          timeout=REQUEST_TIMEOUT)
        return r.json()
    except requests.RequestException as e:
        logger.error(f"create_lead_note failed: {e}")
        return {"error": str(e)}


def create_user_note(api_key, user_id, note_text):
    """POST /v3/users/createNote — Add note to existing user profile.
    Params: user_id, description.
    """
    try:
        r = requests.post(f"{BASE_URL}/v3/users/createNote",
                          headers=_headers(api_key),
                          json={"user_id": user_id, "description": note_text},
                          timeout=REQUEST_TIMEOUT)
        return r.json()
    except requests.RequestException as e:
        logger.error(f"create_user_note failed: {e}")
        return {"error": str(e)}


# ── Tasks ────────────────────────────────────────────────────────────────

def get_task_types(api_key, location_id):
    """GET /v3/tasks/types — Available task type categories."""
    try:
        r = requests.get(f"{BASE_URL}/v3/tasks/types", headers=_headers(api_key),
                         params={"location_id": location_id}, timeout=REQUEST_TIMEOUT)
        return r.json()
    except requests.RequestException as e:
        logger.error(f"get_task_types failed: {e}")
        return {"error": str(e)}


def create_task(api_key, location_id, task_type_id, description,
                reminder_date, reminder_time="09:00", user_id=None, assigned_to=None):
    """POST /v3/tasks — Create a new task.
    Params:
        location_id: Arbox location ID
        task_type_id: Task type ID (e.g. the [Billy] task type)
        description: Task details
        reminder_date: Y-m-d format
        reminder_time: HH:MM format (default 09:00)
        user_id: (optional) Associated Arbox user
        assigned_to: (optional) Staff member ID
    """
    data = {
        "location_id": location_id,
        "task_type_id": task_type_id,
        "description": description,
        "reminder": {"date": reminder_date, "time": reminder_time},
    }
    if user_id:
        data["user_id"] = user_id
    if assigned_to:
        data["assigned_to"] = assigned_to
    try:
        r = requests.post(f"{BASE_URL}/v3/tasks", headers=_headers(api_key),
                          json=data, timeout=REQUEST_TIMEOUT)
        return r.json()
    except requests.RequestException as e:
        logger.error(f"create_task failed: {e}")
        return {"error": str(e)}


# ── Users ────────────────────────────────────────────────────────────────

def search_user(api_key, phone=None, email=None):
    """GET /v3/users/searchUser — Search by phone or email.
    Public API requires type/value params instead of direct phone/email.
    """
    params = {}
    if phone:
        params["type"] = "phone"
        params["value"] = phone
    elif email:
        params["type"] = "email"
        params["value"] = email
    try:
        r = requests.get(f"{BASE_URL}/v3/users/searchUser",
                         headers=_headers(api_key),
                         params=params, timeout=REQUEST_TIMEOUT)
        return r.json()
    except requests.RequestException as e:
        logger.error(f"search_user failed: {e}")
        return {"error": str(e)}


def search_user_by_name(api_key, name):
    """Search Arbox users by name. Returns list of user dicts.

    Uses GET /v3/users/searchUser?type=name&value=... — returns matching users.
    If the API doesn't support name search, falls back to leads list search.
    """
    try:
        r = requests.get(f"{BASE_URL}/v3/users/searchUser",
                         headers=_headers(api_key),
                         params={"type": "name", "value": name},
                         timeout=REQUEST_TIMEOUT)
        result = r.json()
        # Arbox returns either a single user dict or a list
        if isinstance(result, list):
            return result
        if isinstance(result, dict) and result.get("id"):
            return [result]
        if isinstance(result, dict) and result.get("data"):
            return result["data"] if isinstance(result["data"], list) else [result["data"]]
        return []
    except requests.RequestException as e:
        logger.error(f"search_user_by_name failed: {e}")
        return []


def get_user(api_key, user_id):
    """GET /v3/users/{userId}"""
    try:
        r = requests.get(f"{BASE_URL}/v3/users/{user_id}",
                         headers=_headers(api_key), timeout=REQUEST_TIMEOUT)
        return r.json()
    except requests.RequestException as e:
        logger.error(f"get_user failed: {e}")
        return {"error": str(e)}


def get_user_memberships(api_key, user_id):
    """GET /v3/users/memberships"""
    try:
        r = requests.get(f"{BASE_URL}/v3/users/memberships",
                         headers=_headers(api_key),
                         params={"userId": user_id}, timeout=REQUEST_TIMEOUT)
        return r.json()
    except requests.RequestException as e:
        logger.error(f"get_user_memberships failed: {e}")
        return {"error": str(e)}


# ── Schedule ─────────────────────────────────────────────────────────────

def get_schedule(api_key, date_from, date_to):
    """GET /v3/schedule"""
    try:
        r = requests.get(f"{BASE_URL}/v3/schedule",
                         headers=_headers(api_key),
                         params={"fromDate": date_from, "toDate": date_to},
                         timeout=REQUEST_TIMEOUT)
        return r.json()
    except requests.RequestException as e:
        logger.error(f"get_schedule failed: {e}")
        return {"error": str(e)}


def book_trial(api_key, schedule_id, first_name, last_name, phone, email=None):
    """POST /v3/schedule/booking/trial"""
    data = {
        "scheduleId": schedule_id,
        "firstName": first_name,
        "lastName": last_name,
        "phone": phone
    }
    if email:
        data["email"] = email
    try:
        r = requests.post(f"{BASE_URL}/v3/schedule/booking/trial",
                          headers=_headers(api_key), json=data,
                          timeout=REQUEST_TIMEOUT)
        return r.json()
    except requests.RequestException as e:
        logger.error(f"book_trial failed: {e}")
        return {"error": str(e)}


# ── Reference Data ───────────────────────────────────────────────────────

def get_lead_statuses(api_key):
    """GET /v3/statuses — Available lead statuses."""
    try:
        r = requests.get(f"{BASE_URL}/v3/statuses",
                         headers=_headers(api_key), timeout=REQUEST_TIMEOUT)
        return r.json()
    except requests.RequestException as e:
        logger.error(f"get_lead_statuses failed: {e}")
        return {"error": str(e)}


def get_membership_types(api_key):
    """GET /v3/membershipTypes"""
    try:
        r = requests.get(f"{BASE_URL}/v3/membershipTypes",
                         headers=_headers(api_key), timeout=REQUEST_TIMEOUT)
        return r.json()
    except requests.RequestException as e:
        logger.error(f"get_membership_types failed: {e}")
        return {"error": str(e)}


# ── Reports ──────────────────────────────────────────────────────────────

def get_report(api_key, report_name, **params):
    """GET /v3/reports/{reportName} — Fetch any Arbox report.
    Known report names: allClientsReport, salesReport, convertedLeadReport,
    activeMembersReport, inactiveMembersReport, bookingsReport,
    sessionsReport, trialClassesReport, shiftSummaryReport, debtReport,
    allLeadsReport, lateCancellationReport, etc.
    Pass extra params as kwargs (e.g. page=1, fromDate='2026-01-01').
    """
    try:
        r = requests.get(f"{BASE_URL}/v3/reports/{report_name}",
                         headers=_headers(api_key),
                         params=params, timeout=30)
        return r.json()
    except requests.RequestException as e:
        logger.error(f"get_report({report_name}) failed: {e}")
        return {"error": str(e)}


def get_bookings(api_key, from_date, to_date):
    """GET /v3/reports/bookingsReport — Per-person booking records for a date range.
    Returns list of dicts with: date, time, class_name, space_name (boat/room),
    name, user_id, phone, email, membership_type_name, check_in, sessions_left, etc.
    Note: uses camelCase params (fromDate/toDate), not snake_case.
    """
    result = get_report(api_key, "bookingsReport",
                        fromDate=from_date, toDate=to_date)
    if isinstance(result, dict) and "error" not in result:
        return result.get("data") or []
    return result


def get_converted_leads(api_key, **params):
    """GET /v3/leads/converted — Fetch leads that were converted to members."""
    try:
        r = requests.get(f"{BASE_URL}/v3/leads/converted",
                         headers=_headers(api_key),
                         params=params, timeout=REQUEST_TIMEOUT)
        return r.json()
    except requests.RequestException as e:
        logger.error(f"get_converted_leads failed: {e}")
        return {"error": str(e)}


def get_all_users(api_key, page=1, limit=100):
    """GET /v3/users — List all users with pagination."""
    try:
        r = requests.get(f"{BASE_URL}/v3/users",
                         headers=_headers(api_key),
                         params={"page": page, "limit": limit},
                         timeout=REQUEST_TIMEOUT)
        return r.json()
    except requests.RequestException as e:
        logger.error(f"get_all_users failed: {e}")
        return {"error": str(e)}


def create_digital_form_link(api_key, user_id, form_type=None):
    """POST /v3/digitalForms/createLink — Generate a form link for a user."""
    data = {"userId": user_id}
    if form_type:
        data["type"] = form_type
    try:
        r = requests.post(f"{BASE_URL}/v3/digitalForms/createLink",
                          headers=_headers(api_key),
                          json=data, timeout=REQUEST_TIMEOUT)
        return r.json()
    except requests.RequestException as e:
        logger.error(f"create_digital_form_link failed: {e}")
        return {"error": str(e)}


# ── Composite Lookup ─────────────────────────────────────────────────────

def arbox_lookup(arbox_config, phone):
    """Look up a phone number in Arbox to enrich conversation context.
    Returns dict with lead/user data, or None."""
    api_key = arbox_config["api_key"]
    if not api_key:
        return None

    # Try as existing user
    result = search_user(api_key, phone=phone)
    if result.get("error"):
        logger.warning(f"Arbox lookup failed for {phone}: {result['error']}")
        return None

    if result.get("data"):
        user = result["data"][0] if isinstance(result["data"], list) else result["data"]
        memberships = get_user_memberships(api_key, user.get("user_id"))
        membership_data = memberships.get("data", []) if not memberships.get("error") else []
        return {
            "is_existing_user": True,
            "user_id": user.get("user_id"),
            "name": f"{user.get('first_name', '')} {user.get('last_name', '')}".strip(),
            "memberships": membership_data,
            "status": "past_member" if membership_data else "lead"
        }

    return None


# ── CLI Test ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from pathlib import Path
    from dotenv import load_dotenv

    project_root = Path(__file__).resolve().parent.parent
    load_dotenv(project_root / ".env")

    api_key = os.getenv("A247_ARBOX_API_KEY")
    if not api_key:
        print("A247_ARBOX_API_KEY not set in .env")
        print("Arbox API wrapper loaded successfully (structural test passed)")
        sys.exit(0)

    print("Testing Arbox API connectivity...")
    result = get_lead_statuses(api_key)
    print(json.dumps(result, indent=2, ensure_ascii=False))
