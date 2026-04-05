#!/usr/bin/env python3
"""
Flask server for the studio summary configuration dashboard.

Endpoints:
    GET  /              — Serve dashboard HTML
    GET  /api/config    — Current config + resolved module states
    GET  /api/templates — Available templates
    POST /api/config    — Save template + module overrides
    POST /api/preview   — Dry-run: collect data + format message
    GET  /health        — Health check

Usage:
    python dashboard_server.py
"""

import os
import sys
import json
import logging
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
STATIC_DIR = REPO_ROOT / "static"
CONFIG_PATH = REPO_ROOT / "config.json"
TEMPLATES_DIR = REPO_ROOT / "templates"

sys.path.insert(0, str(REPO_ROOT))

from flask import Flask, jsonify, request, send_from_directory
from modules import resolve_config, get_all_modules, get_enabled_modules, load_template, MODULE_ORDER

app = Flask(__name__, static_folder=str(STATIC_DIR))
logging.basicConfig(level=logging.INFO)


def _read_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def _write_config(config):
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
        f.write("\n")


def _get_available_templates():
    templates = []
    for f in sorted(TEMPLATES_DIR.glob("*.json")):
        with open(f) as fh:
            t = json.load(fh)
            templates.append({
                "id": t.get("template_id", f.stem),
                "name_he": t.get("name_he", f.stem),
                "modules": t.get("modules", {}),
            })
    return templates


@app.route("/")
def index():
    return send_from_directory(str(STATIC_DIR), "dashboard.html")


@app.route("/api/config", methods=["GET"])
def get_config():
    config = _read_config()
    resolved = resolve_config(config)
    all_modules = get_all_modules()

    modules_list = []
    template_id = config.get("template", "general_fitness")
    template = load_template(template_id)
    template_modules = template.get("modules", {})
    overrides = config.get("module_overrides", {})

    for mod in all_modules:
        meta = mod.MODULE_META
        mid = meta["id"]
        mod_resolved = resolved.get(mid, {})
        mod_template = template_modules.get(mid, {})
        mod_override = overrides.get(mid, {})

        params = {}
        for key, val in meta.get("default_params", {}).items():
            params[key] = {
                "value": mod_resolved.get(key, val),
                "default": val,
                "template_value": mod_template.get(key, val),
                "is_override": key in mod_override,
            }

        modules_list.append({
            "id": mid,
            "name_he": meta.get("name_he", mid),
            "description_he": meta.get("description_he", ""),
            "enabled": mod_resolved.get("enabled", False),
            "compare": mod_resolved.get("compare", False),
            "supports_compare": meta.get("supports_compare", False),
            "default_enabled": meta.get("default_enabled", False),
            "template_enabled": mod_template.get("enabled", meta.get("default_enabled", False)),
            "is_override": mid in overrides,
            "params": params,
        })

    return jsonify({
        "template": template_id,
        "available_templates": _get_available_templates(),
        "modules": modules_list,
        "client_name": config.get("client_name", ""),
    })


@app.route("/api/templates", methods=["GET"])
def get_templates():
    return jsonify(_get_available_templates())


@app.route("/api/config", methods=["POST"])
def save_config():
    payload = request.get_json()
    if not payload:
        return jsonify({"error": "No JSON body"}), 400

    config = _read_config()
    if "template" in payload:
        config["template"] = payload["template"]
    if "module_overrides" in payload:
        config["module_overrides"] = payload["module_overrides"]

    _write_config(config)
    return jsonify({"status": "saved"})


@app.route("/api/preview", methods=["POST"])
def preview():
    payload = request.get_json() or {}

    config = _read_config()
    if "template" in payload:
        config["template"] = payload["template"]
    if "module_overrides" in payload:
        config["module_overrides"] = payload["module_overrides"]

    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")

    api_key = os.getenv("A247_ARBOX_API_KEY")
    if not api_key:
        return jsonify({"error": "A247_ARBOX_API_KEY not set"}), 500

    try:
        from data_collector import collect_studio_data
        from report_formatter import format_telegram_message

        data = collect_studio_data(api_key, config)
        message = format_telegram_message(data, config)
        return jsonify({"message": message})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")

    port = int(os.getenv("DASHBOARD_PORT", 5020))
    print(f"Dashboard server starting on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)
