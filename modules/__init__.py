#!/usr/bin/env python3
"""Module registry — discovers, loads, and resolves module configurations."""

import json
import logging
import importlib
from pathlib import Path

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
MODULES_DIR = Path(__file__).resolve().parent

# Module load order (determines display order in report)
MODULE_ORDER = [
    "lead_pipeline",
    "revenue",
    "expiring",
    "retention",
    "operations",
    "debt",
    "late_cancellations",
    "renewals_forecast",
    "birthdays",
    "members_on_hold",
    "staff",
]

# Lazy-loaded module cache
_module_cache = {}


def _load_module(module_id):
    """Import a module file and return it."""
    if module_id in _module_cache:
        return _module_cache[module_id]
    try:
        mod = importlib.import_module(f"modules.{module_id}")
        _module_cache[module_id] = mod
        return mod
    except ImportError as e:
        logger.error(f"Failed to import module '{module_id}': {e}")
        return None


def get_all_modules():
    """Return all available modules in display order."""
    modules = []
    for module_id in MODULE_ORDER:
        mod = _load_module(module_id)
        if mod and hasattr(mod, "MODULE_META"):
            modules.append(mod)
    return modules


def load_template(template_id):
    """Load a template JSON file."""
    template_path = TEMPLATES_DIR / f"{template_id}.json"
    if not template_path.exists():
        logger.warning(f"Template '{template_id}' not found at {template_path}")
        return {}
    with open(template_path) as f:
        return json.load(f)


def resolve_config(config):
    """Resolve module configurations from template + overrides.

    Args:
        config: dict with optional 'template' and 'module_overrides' keys

    Returns:
        dict mapping module_id → resolved params dict (includes 'enabled', 'compare', etc.)
    """
    # Start with template defaults
    template_id = config.get("template", "general_fitness")
    template = load_template(template_id)
    template_modules = template.get("modules", {})

    # Apply per-studio overrides
    overrides = config.get("module_overrides", {})

    resolved = {}
    for module_id in MODULE_ORDER:
        mod = _load_module(module_id)
        if not mod:
            continue

        meta = mod.MODULE_META

        # Base: module defaults
        module_config = {
            "enabled": meta.get("default_enabled", False),
            "compare": False,
            **meta.get("default_params", {}),
        }

        # Layer: template settings
        if module_id in template_modules:
            module_config.update(template_modules[module_id])

        # Layer: per-studio overrides
        if module_id in overrides:
            module_config.update(overrides[module_id])

        resolved[module_id] = module_config

    return resolved


def get_enabled_modules(resolved_config):
    """Return list of (module, config) tuples for enabled modules, in display order."""
    enabled = []
    for module_id in MODULE_ORDER:
        config = resolved_config.get(module_id, {})
        if config.get("enabled", False):
            mod = _load_module(module_id)
            if mod:
                enabled.append((mod, config))
    return enabled
