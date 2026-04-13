#!/usr/bin/env python3
"""
Studio report formatter — modular system that formats collected data as Hebrew Telegram message.

Loops over enabled modules, calls each module's format() function, joins with section separators.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

from modules import resolve_config, get_enabled_modules
from modules._helpers import date_full_he


def format_telegram_message(data, config):
    """Format studio data dict into Hebrew Telegram HTML message.

    Args:
        data: dict returned by collect_studio_data()
        config: dict with 'template' and optional 'module_overrides'

    Returns:
        str — formatted Telegram HTML message
    """
    period = data.get("period", {})
    resolved = resolve_config(config)
    enabled = get_enabled_modules(resolved)

    RLM = "\u200f"
    lines = []

    # Header
    lines.append(f"{RLM}<b>סיכום סטודיו — {date_full_he(period.get('today', ''))}</b>")
    lines.append("")

    for mod, mod_config in enabled:
        module_id = mod.MODULE_META["id"]
        module_data = data.get(module_id, {})

        # Skip modules with errors or no data
        if not module_data or "error" in module_data:
            continue

        # Get comparison data if available
        compare_data = data.get(f"{module_id}_compare")

        try:
            section_lines = mod.format(module_data, compare_data)
            if section_lines:
                lines.extend(section_lines)
                lines.append("")  # blank line between sections
        except Exception:
            pass  # skip broken formatters silently

    # Remove trailing blank line
    while lines and lines[-1] == "":
        lines.pop()

    return "\n".join(lines)
