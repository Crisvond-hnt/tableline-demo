"""TheFork fixture adapter.

TheFork documents a partner B2B API. This module does not call it.
It reads the JSON fixtures, checks that they are labeled synthetic,
and hands them to the shared reservation-event recorder.
"""

from __future__ import annotations

import json
from pathlib import Path

from integrations.events import SCHEMA, hold_file, record_event
from integrations.store import Store


def ingest_dir(store: Store, directory: Path) -> list:
    """Every file gets a result. A file that cannot be read is held, and the next one is still read."""
    return [ingest_file(store, path) for path in sorted(directory.glob("*.json"))]


def ingest_file(store: Store, path: Path) -> dict:
    try:
        data = json.loads(path.read_text())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        return hold_file(store, "thefork", path.name, "file is not readable JSON (%s)" % type(error).__name__)
    if not isinstance(data, dict):
        return hold_file(store, "thefork", path.name, "file is not a JSON object")
    event = {
        "schema": SCHEMA,
        "provider": data.get("provider"),
        "source": "thefork-fixture",
        "provider_event_id": data.get("provider_event_id"),
        "kind": data.get("kind"),
        "reservation_id": data.get("reservation_id"),
        "source_message_time": data.get("source_message_time") or data.get("received_at"),
        "service_date": data.get("service_date"),
        "time": data.get("time"),
        "party": data.get("party"),
        "guest": data.get("guest") or "",
        "live": data.get("live"),
        "synthetic": data.get("synthetic"),
        "freshness": (
            "Synthetic TheFork-shaped notice. source_message_time %s is the time written "
            "on the fixture, not a webhook delivery. Not a response from api.thefork.io."
            % (data.get("source_message_time") or data.get("received_at") or "missing")
        ),
    }
    if data.get("provider") != "thefork":
        event["provider"] = data.get("provider") or "thefork"
        event["kind"] = "unrecognized"
    return record_event(store, event)
