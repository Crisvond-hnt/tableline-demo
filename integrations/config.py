"""Load a restaurant config. Unknown rules are allowed."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

RULE_KEYS = (
    "opening_hours",
    "service_windows",
    "party_size_limit",
    "turn_time_minutes",
    "buffers",
    "closed_dates",
    "table_constraints",
    "service_areas",
    "capacities",
    "approval_roles",
    "sources",
    "daily_output",
)

_DAILY = {"pdf", "ics", "both"}
_SOURCE_STATUS = {"not_connected", "manual", "fixture"}
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def config_path(root: Path | None = None) -> Path:
    override = os.environ.get("TABLELINE_CONFIG")
    if override and root is None:
        return Path(override)
    return (root or ROOT) / "fixtures" / "restaurant.json"


def load_config(root: Path | None = None) -> dict:
    path = config_path(root)
    data = json.loads(path.read_text())
    errors = validate_config(data)
    if errors:
        raise ValueError(path.name + ": " + "; ".join(errors))
    return data


def load_snapshot(root: Path | None = None) -> dict:
    base = root or ROOT
    path = base / "fixtures" / "snapshot.json"
    data = json.loads(path.read_text())
    if data.get("live") is not False or data.get("synthetic") is not True:
        raise ValueError("snapshot.json must be a synthetic, non-live snapshot")
    if not data.get("generated_at"):
        raise ValueError("snapshot.json needs generated_at")
    return data


def validate_config(data: dict) -> list:
    errors = []
    if not isinstance(data, dict):
        return ["configuration must be a JSON object"]
    if data.get("contains_guest_data") is True:
        errors.append("contains_guest_data must not be true")
    if data.get("synthetic") is not True and data.get("contains_guest_data") is not False:
        errors.append("a file that is not synthetic must set contains_guest_data to false")
    if not str(data.get("restaurant") or "").strip():
        errors.append("restaurant name is missing")
    if not str(data.get("timezone") or "").strip():
        errors.append("timezone is missing")
    rules = data.get("rules")
    if not isinstance(rules, dict):
        errors.append("rules must be an object")
        rules = {}
    for key in RULE_KEYS:
        if key not in rules:
            errors.append("rules.%s is missing" % key)
            continue
        errors.extend(_check_rule(key, rules[key]))
    blob = json.dumps(data)
    for address in _EMAIL.findall(blob):
        domain = address.rsplit("@", 1)[-1].lower()
        if domain not in ("example.test", "example.com", "example.invalid"):
            errors.append("email address is not allowed in configuration")
    return errors


def classify_rules(data: dict) -> dict:
    rules = data.get("rules") or {}
    unknown = [key for key in RULE_KEYS if rules.get(key) == "unknown"]
    set_keys = [key for key in RULE_KEYS if key in rules and rules.get(key) != "unknown"]
    return {"unknown": unknown, "set": set_keys}


def _check_rule(key: str, value) -> list:
    if value == "unknown":
        return []
    if key == "daily_output":
        if value not in _DAILY:
            return ["rules.daily_output must be unknown, pdf, ics, or both"]
        return []
    if key == "service_areas":
        return _check_areas(value)
    if key == "approval_roles":
        if not isinstance(value, list) or not value or not all(isinstance(item, str) and item.strip() for item in value):
            return ["rules.approval_roles must be unknown or a list of role names"]
        return []
    if key == "sources":
        return _check_sources(value)
    if isinstance(value, str) and value.strip():
        return []
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return []
    return ["rules.%s must be unknown or a stated value" % key]


def _check_areas(value) -> list:
    if not isinstance(value, list) or not value:
        return ["rules.service_areas must be unknown or a list of areas"]
    errors = []
    for area in value:
        if not isinstance(area, dict) or not str(area.get("name") or "").strip():
            errors.append("each service area needs a name")
            continue
        capacity = area.get("capacity")
        if not isinstance(capacity, int) or isinstance(capacity, bool) or capacity < 1:
            errors.append("service area %s needs a capacity" % area.get("name"))
    return errors


def _check_sources(value) -> list:
    if not isinstance(value, list) or not value:
        return ["rules.sources must be unknown or a list of sources"]
    errors = []
    for source in value:
        if not isinstance(source, dict) or not str(source.get("name") or "").strip():
            errors.append("each source needs a name")
            continue
        if source.get("status") not in _SOURCE_STATUS:
            errors.append("source %s status must be not_connected, manual, or fixture" % source.get("name"))
    return errors
