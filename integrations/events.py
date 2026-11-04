"""One reservation-event shape for every source adapter.

Adapters translate a fixture into this shape. The ledger stores accepted
events as notices. A notice is intake, not an availability search.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from integrations.store import Store


SCHEMA = "tableline.reservation_event.v1"
KINDS = {"created", "updated", "cancelled"}
_DATE = re.compile(r"20\d{2}-\d{2}-\d{2}")
_TIME = re.compile(r"([01]\d|2[0-3]):[0-5]\d")


def event_key(event: dict) -> str:
    return "event:%s:%s:%s:%s" % (
        event.get("provider") or "",
        event.get("source") or "",
        event.get("kind") or "",
        event.get("provider_event_id") or "",
    )


def record_event(store: Store, event: dict) -> dict:
    key = event_key(event)
    provider_event_id = str(event.get("provider_event_id") or "")
    provider = str(event.get("provider") or "")
    if key in store.data["seen_message_ids"]:
        return {
            "accepted": True,
            "duplicate": True,
            "message_id": provider_event_id,
            "provider": provider,
            "dedup_key": key,
        }

    problems = _problems(event)
    if problems:
        reason = "; ".join(problems)
        if not _review_open(store, key, reason):
            _review(store, event, reason, key)
        return {
            "accepted": False,
            "reason": reason,
            "message_id": provider_event_id,
            "provider": provider,
            "dedup_key": key,
            "replayable": True,
        }

    notice = {
        "schema": SCHEMA,
        "ingested_at": _now(),
        "source_message_time": event["source_message_time"],
        "source_message_time_label": "sender or fixture timestamp, not a mailbox delivery time",
        "actor": "adapter",
        "provider": event["provider"],
        "source": event["source"],
        "message_id": provider_event_id,
        "reservation_id": event["reservation_id"],
        "notice": event["kind"],
        "service_date": event["service_date"],
        "time": event["time"],
        "party": event["party"],
        "guest": event.get("guest") or "",
        "live": False,
        "synthetic": True,
        "freshness": event["freshness"],
        "dedup_key": key,
    }
    store.data["notices"].append(notice)
    store.data["seen_message_ids"][key] = "notice:%s:%s" % (event["provider"], event["reservation_id"])
    store.save()
    return {"accepted": True, "duplicate": False, "notice": notice, "provider": provider, "dedup_key": key}


def valid_service_date(value) -> bool:
    if not isinstance(value, str) or not _DATE.fullmatch(value):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return True


def valid_clock(value) -> bool:
    return isinstance(value, str) and bool(_TIME.fullmatch(value))


def valid_timestamp(value) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _problems(event: dict) -> list:
    problems = []
    if event.get("schema") != SCHEMA:
        problems.append("schema is not %s" % SCHEMA)
    if event.get("live") is not False or event.get("synthetic") is not True:
        problems.append("event must be a synthetic fixture")
    if event.get("provider") not in ("umai", "thefork"):
        problems.append("provider is not a known fixture adapter")
    if not event.get("provider_event_id"):
        problems.append("missing provider event id")
    if not event.get("source"):
        problems.append("missing source label")
    if not valid_timestamp(event.get("source_message_time")):
        problems.append("source_message_time must be an ISO timestamp with a timezone")
    if not event.get("freshness"):
        problems.append("missing freshness")
    kind = event.get("kind")
    if kind not in KINDS:
        problems.append("unrecognized notice kind")
        return problems
    if not event.get("reservation_id"):
        problems.append("event is missing reservation id")
    if not valid_service_date(event.get("service_date")):
        problems.append("service date is not a real YYYY-MM-DD date")
    if not valid_clock(event.get("time")):
        problems.append("time is not HH:MM")
    party = event.get("party")
    if not isinstance(party, int) or isinstance(party, bool) or party < 1:
        problems.append("event is missing party")
    return problems


def _review(store: Store, event: dict, reason: str, key: str) -> None:
    store.data["review"].append(
        {
            "at": _now(),
            "source": event.get("source") or "",
            "provider": event.get("provider") or "",
            "message_id": event.get("provider_event_id") or "",
            "dedup_key": key,
            "reason": reason,
            "replayable": True,
        }
    )
    store.save()


def hold_file(store: Store, provider: str, source: str, reason: str, message_id: str = "") -> dict:
    """Hold a file that never became an event. The rest of the batch continues.

    The same file with the same reason is listed once. Nothing is marked seen,
    so a corrected copy can be ingested later.
    """
    key = "file:%s:%s" % (provider, source)
    if not _review_open(store, key, reason):
        store.data["review"].append(
            {
                "at": _now(),
                "source": source,
                "provider": provider,
                "message_id": message_id,
                "dedup_key": key,
                "reason": reason,
                "replayable": True,
            }
        )
        store.save()
    return {
        "accepted": False,
        "reason": reason,
        "message_id": message_id,
        "provider": provider,
        "source": source,
        "replayable": True,
    }


def _review_open(store: Store, key: str, reason: str) -> bool:
    for item in store.data["review"]:
        if item.get("dedup_key") == key and item.get("reason") == reason:
            return True
    return False


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
