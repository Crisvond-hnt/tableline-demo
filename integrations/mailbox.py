"""Parse notice mail against the synthetic contract in the restaurant config.

Sender, subject, and body all have to match the configured contract.
"""

from __future__ import annotations

import re
from datetime import timezone
from email import message_from_bytes
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path

from integrations.events import SCHEMA, hold_file, record_event
from integrations.store import Store


_STATUS = {"new": "created", "edited": "updated", "cancelled": "cancelled"}


def _body(message) -> str:
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True) or b""
                return payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        return ""
    payload = message.get_payload(decode=True) or b""
    return payload.decode(message.get_content_charset() or "utf-8", errors="replace")


def _fields(body: str) -> dict:
    found = {}
    for line in body.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        found[key.strip().lower()] = value.strip()
    return found


def parse_notice(raw: bytes, config: dict) -> dict:
    """Return a notice, or {accepted: False, reason, message_id}."""
    message = message_from_bytes(raw)
    message_id = (message.get("Message-ID") or "").strip()
    sender = parseaddr(message.get("From") or "")[1].lower()
    domain = sender.split("@")[-1] if "@" in sender else ""
    subject = re.sub(r"\s+", " ", (message.get("Subject") or "").strip())
    allowed = [item.lower() for item in config["mailbox"]["allowed_from_domains"]]
    pattern = re.compile(config["mailbox"]["subject_pattern"])
    matched = pattern.match(subject)
    fields = _fields(_body(message))

    def reject(reason: str) -> dict:
        return {"accepted": False, "reason": reason, "message_id": message_id, "subject": subject}

    if not message_id:
        return reject("missing message id")
    if domain not in allowed:
        return reject("sender domain is not the configured notice domain")
    if not matched:
        return reject("subject does not match the configured notice pattern")
    word, reservation_id = matched.group(1), matched.group(2)
    required = ("restaurant", "reservation", "status", "date", "time", "party")
    missing = [name for name in required if not fields.get(name)]
    if missing:
        return reject("body is missing " + ", ".join(missing))
    if fields["restaurant"] != config["restaurant"]:
        return reject("restaurant line does not match configuration")
    if fields["status"] != word or fields["reservation"] != reservation_id:
        return reject("subject and body do not name the same notice")
    if not re.fullmatch(r"20\d{2}-\d{2}-\d{2}", fields["date"]):
        return reject("date is not YYYY-MM-DD")
    if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", fields["time"]):
        return reject("time is not HH:MM")
    if not fields["party"].isdigit():
        return reject("party is not a number")
    source_message_time = _source_message_time(message.get("Date"))
    if not source_message_time:
        return reject("notice has no parseable Date header")
    return {
        "accepted": True,
        "message_id": message_id,
        "reservation_id": reservation_id,
        "notice": _STATUS[word],
        "service_date": fields["date"],
        "time": fields["time"],
        "party": int(fields["party"]),
        "guest": fields.get("guest", ""),
        "sender": sender,
        "source_message_time": source_message_time,
    }


def ingest_file(store: Store, path: Path, config: dict) -> dict:
    try:
        raw = path.read_bytes()
    except OSError as error:
        return hold_file(store, "umai", path.name, "file could not be read (%s)" % type(error).__name__)
    parsed = parse_notice(raw, config)
    if not parsed["accepted"]:
        return hold_file(store, "umai", path.name, parsed["reason"], parsed.get("message_id", ""))
    return record_event(
        store,
        {
            "schema": SCHEMA,
            "provider": "umai",
            "source": "umai-email-fixture",
            "provider_event_id": parsed["message_id"],
            "kind": parsed["notice"],
            "reservation_id": parsed["reservation_id"],
            "source_message_time": parsed["source_message_time"],
            "service_date": parsed["service_date"],
            "time": parsed["time"],
            "party": parsed["party"],
            "guest": parsed["guest"],
            "live": False,
            "synthetic": True,
            "freshness": (
                "Synthetic UMAI-shaped email. The Date header %s is the sender's timestamp, "
                "not proof a mailbox received it. This file was not collected by polling. "
                "The real UMAI subject and body were not verified."
                % parsed["source_message_time"]
            ),
        },
    )


def ingest_dir(store: Store, directory: Path, config: dict) -> list:
    paths = sorted(directory.glob("*.eml"))
    return [ingest_file(store, path, config) for path in paths]


def _source_message_time(value) -> str:
    if not value:
        return ""
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        return ""
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat()
