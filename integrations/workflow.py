"""Intake, the snapshot check, and the approval steps.

approve matches the offered slot. attach_reference matches the id against
this folder's store and snapshot. confirm records a simulated send after that.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone

from integrations.events import valid_clock, valid_service_date, valid_timestamp
from integrations.store import Store


_PARTY_WORDS = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8}
_EVENT_WORDS = ("wedding", "private dining", "private event", "buyout")
_REF = re.compile(r"^NL-[0-9]+$")


class WorkflowError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def classify(text: str, subject: str = "") -> str:
    blob = (subject + " " + text).lower()
    if any(word in blob for word in _EVENT_WORDS):
        return "event_inquiry"
    if "cancel" in blob:
        return "reservation_change"
    if any(word in blob for word in ("table", "book", "reservation", "tonight")):
        return "direct_reservation"
    return "non_reservation"


def _party(text: str):
    matched = re.search(r"\bfor (\d+|two|three|four|five|six|seven|eight)\b", text.lower())
    if not matched:
        return None
    token = matched.group(1)
    return int(token) if token.isdigit() else _PARTY_WORDS[token]


def _time(text: str):
    matched = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", text)
    if not matched:
        return None
    return "%02d:%s" % (int(matched.group(1)), matched.group(2))


def _date(text: str, received_at: str, timezone_name: str):
    matched = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", text)
    if matched:
        return matched.group(1)
    if "tonight" in text.lower() or "today" in text.lower():
        from zoneinfo import ZoneInfo

        moment = datetime.fromisoformat(received_at)
        return moment.astimezone(ZoneInfo(timezone_name)).date().isoformat()
    return None


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _request_id(channel: str, thread_id: str) -> str:
    digest = hashlib.sha256((channel + ":" + thread_id).encode("utf-8")).hexdigest()[:8]
    return "req_" + digest


def _history(actor: str, event: str, detail: str) -> dict:
    return {"at": _now(), "actor": actor, "event": event, "detail": detail}


def _public_request(item: dict) -> dict:
    hidden = {"authorized_text"}
    return {key: value for key, value in item.items() if key not in hidden}


def intake(store: Store, message: dict, config: dict, snapshot: dict) -> dict:
    if message.get("synthetic") is not True or message.get("live") is not False:
        raise WorkflowError("fixture must be labeled synthetic and not live")
    message_id = message["message_id"]
    if message_id in store.data["seen_message_ids"]:
        existing = store.request_for_message(message_id)
        return {"duplicate": True, "request": _public_request(existing) if existing else None}
    existing = store.request_by_thread(message["channel"], message["thread_id"])
    if existing:
        return _follow_up(store, existing, message, config, snapshot)
    kind = classify(message.get("text", ""), message.get("subject", ""))
    item = {
        "id": _request_id(message["channel"], message["thread_id"]),
        "received_at": message["received_at"],
        "channel": message["channel"],
        "thread_id": message["thread_id"],
        "message_ids": [message_id],
        "dedup_key": message["channel"] + ":" + message_id,
        "classification": kind,
        "status": "received",
        "guest_name": message.get("guest_name", ""),
        "service_date": _date(message.get("text", ""), message["received_at"], config["timezone"]),
        "time": _time(message.get("text", "")),
        "party": _party(message.get("text", "")),
        "missing": [],
        "history": [],
        "offered": [],
        "availability": None,
        "approval": None,
        "booking_reference": None,
        "authorized_text": None,
        "outbound": None,
        "follow_up_due": None,
        "questions": [],
        "restaurant": config["restaurant"],
    }
    item["history"].append(_history("coordinator", "received", message["channel"] + " " + message_id))
    _classify_status(item)
    store.data["requests"].append(item)
    store.data["seen_message_ids"][message_id] = item["id"]
    store.save()
    return {"duplicate": False, "request": _public_request(item)}


def _classify_status(item: dict) -> None:
    item["history"].append(_history("coordinator", "classified", item["classification"]))
    if item["classification"] == "event_inquiry":
        item["status"] = "awaiting_staff_questions"
        return
    if item["classification"] != "direct_reservation":
        item["status"] = "needs_staff_review"
        return
    missing = []
    if not item["service_date"]:
        missing.append("service date")
    if not item["time"]:
        missing.append("time")
    if not item["party"]:
        missing.append("party size")
    item["missing"] = missing
    item["status"] = "needs_information" if missing else "classified"


def _follow_up(store: Store, item: dict, message: dict, config: dict, snapshot: dict) -> dict:
    item["message_ids"].append(message["message_id"])
    item["history"].append(_history("coordinator", "follow_up", message["message_id"]))
    store.data["seen_message_ids"][message["message_id"]] = item["id"]
    if item["classification"] == "direct_reservation":
        new_time = _time(message.get("text", ""))
        if new_time:
            item["time"] = new_time
            item["missing"] = [name for name in item["missing"] if name != "time"]
            if item["service_date"] and item["party"]:
                _check_into(store, item, snapshot, config)
    store.save()
    return {"duplicate": False, "follow_up": True, "request": _public_request(item)}


def check(store: Store, request_id: str, snapshot: dict, config: dict | None = None) -> dict:
    item = _require(store, request_id)
    if item["classification"] != "direct_reservation":
        raise WorkflowError("availability is only checked for a direct reservation")
    if item["missing"]:
        item["status"] = "needs_information"
        store.save()
        raise WorkflowError("missing " + ", ".join(item["missing"]))
    _check_into(store, item, snapshot, config)
    store.save()
    return _public_request(item)


def _check_into(store: Store, item: dict, snapshot: dict, config: dict | None = None) -> None:
    if snapshot.get("live") is not False:
        item["status"] = "needs_staff_review"
        item["history"].append(_history("booking", "availability", "source was not labeled as a snapshot"))
        return
    if item["service_date"] != snapshot["service_date"]:
        item["status"] = "needs_staff_review"
        item["availability"] = {"live": False, "reason": "snapshot covers a different service date"}
        item["history"].append(_history("booking", "availability", "snapshot date does not match"))
        return
    if not valid_clock(item.get("time")):
        item["status"] = "needs_staff_review"
        item["history"].append(_history("booking", "availability", "request time is not HH:MM"))
        return
    rows, blocked = reconcile(store, snapshot, item["service_date"], config)
    overlaps = []
    for row in rows.values():
        if row.get("end") and _inside(item["time"], row["start"], row["end"]):
            overlaps.append(
                {
                    "reservation_id": row["reservation_id"],
                    "provider": row["provider"],
                    "start": row["start"],
                    "end": row["end"],
                }
            )
    uncertain_ids = _uncertain_ids(item["time"], rows)
    offered = []
    withheld = []
    too_large = []
    requested_slot = "not a slot the house offers"
    if not blocked:
        for slot in snapshot.get("candidate_slots") or []:
            if not valid_clock(slot.get("time")):
                continue
            is_requested = slot["time"] == item["time"]
            party_max = slot.get("party_max")
            if not isinstance(party_max, int) or isinstance(party_max, bool) or item["party"] > party_max:
                too_large.append({"time": slot["time"], "party_max": party_max})
                if is_requested:
                    requested_slot = "party of %s is above the slot maximum of %s" % (item["party"], party_max)
                continue
            if _slot_is_clear(slot["time"], rows):
                offer = {"date": snapshot["service_date"], "time": slot["time"], "party": item["party"]}
                if is_requested:
                    offered.insert(0, offer)
                    requested_slot = "offered"
                else:
                    offered.append(offer)
            else:
                withheld.append(
                    {
                        "time": slot["time"],
                        "uncertain_reservation_ids": _uncertain_ids(slot["time"], rows),
                    }
                )
                if is_requested:
                    requested_slot = "taken or withheld"
    if requested_slot == "not a slot the house offers" and overlaps:
        requested_slot = "conflicts with " + ", ".join(row["reservation_id"] for row in overlaps)
    item["offered"] = offered
    item["availability"] = {
        "live": False,
        "source": snapshot["source"],
        "generated_at": snapshot["generated_at"],
        "timezone": snapshot["timezone"],
        "conflicts": overlaps,
        "uncertain_reservation_ids": uncertain_ids,
        "withheld_slots": withheld,
        "slots_above_party_max": too_large,
        "requested_slot": requested_slot,
        "blocked_reason": blocked,
        "notice_feed": _notice_feed(store),
        "duration_rule": "verified" if _verified_minutes(config) else "unknown",
    }
    if blocked or uncertain_ids or not offered:
        item["status"] = "needs_staff_review"
    else:
        item["status"] = "awaiting_staff_booking_approval"
    if blocked:
        detail = blocked
    elif overlaps:
        detail = "conflicts " + ",".join(row["reservation_id"] for row in overlaps)
    elif uncertain_ids:
        detail = "uncertain " + ",".join(uncertain_ids)
    elif not offered:
        detail = "no slot offered; requested time " + requested_slot
    else:
        detail = "no overlap"
    item["history"].append(_history("booking", "availability_checked", detail))


def _notice_feed(store: Store) -> dict:
    stamps = [
        notice.get("source_message_time")
        for notice in store.data["notices"]
        if valid_timestamp(notice.get("source_message_time"))
    ]
    return {
        "accepted": len(store.data["notices"]),
        "latest_source_message_time": max(stamps) if stamps else None,
        "freshness": (
            "source_message_time is the timestamp written on the fixture or the email Date header. "
            "ingested_at is when this process recorded the file. No mailbox was polled and no booking API was called."
        ),
    }


def _inside(moment: str, start: str, end: str) -> bool:
    return start <= moment < end


def _verified_minutes(config: dict | None) -> int | None:
    rules = (config or {}).get("rules") or {}
    if rules.get("turn_time_verified") is not True:
        return None
    value = rules.get("turn_time_minutes")
    if isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 24 * 60:
        return value
    return None


def _add_minutes(moment: str, minutes: int) -> str | None:
    hour, minute = [int(part) for part in moment.split(":")]
    start = datetime(2026, 1, 1, hour, minute)
    end = start + timedelta(minutes=minutes)
    if end.date() != start.date():
        return None
    return end.strftime("%H:%M")


def _row_key(provider: str, reservation_id: str) -> str:
    return "%s:%s" % (provider, reservation_id)


def _compare_time(left: str, right: str) -> int:
    left_dt = datetime.fromisoformat(left)
    right_dt = datetime.fromisoformat(right)
    if left_dt < right_dt:
        return -1
    if left_dt > right_dt:
        return 1
    return 0


def reconcile(store: Store, snapshot: dict, service_date: str, config: dict | None = None) -> tuple:
    """Snapshot rows, then notices ordered by source_message_time.

    Returns (rows, blocked_reason). blocked_reason is set when the feed cannot
    be ordered. Rows with no verified duration have end None.
    """
    house = snapshot.get("provider") or "house"
    generated = snapshot.get("generated_at")
    rows = {}
    problems = []
    if not valid_timestamp(generated):
        return {}, "snapshot generated_at is missing or has no timezone"
    if not valid_service_date(service_date):
        return {}, "service date is not a real YYYY-MM-DD date"

    for booking in snapshot.get("bookings") or []:
        if booking.get("service_date") != service_date or booking.get("status") != "booked":
            continue
        if not valid_clock(booking.get("start")) or not valid_clock(booking.get("end")):
            problems.append(booking.get("reservation_id") or "snapshot row" + " has an invalid window")
            continue
        key = _row_key(house, booking["reservation_id"])
        rows[key] = {
            "reservation_id": booking["reservation_id"],
            "provider": house,
            "start": booking["start"],
            "end": booking["end"],
            "party": booking.get("party"),
            "guest": booking.get("guest_name", ""),
            "source": snapshot.get("source") or "snapshot",
            "duration_known": True,
            "as_of": generated,
        }

    grouped = {}
    for notice in store.data["notices"]:
        if notice.get("service_date") != service_date:
            continue
        if not valid_timestamp(notice.get("source_message_time")) or not valid_clock(notice.get("time")):
            problems.append((notice.get("reservation_id") or "notice") + " has an invalid time")
            continue
        if notice.get("provider") not in ("umai", "thefork") or not notice.get("reservation_id"):
            problems.append("notice is missing a provider or reservation id")
            continue
        grouped.setdefault(_row_key(notice["provider"], notice["reservation_id"]), []).append(notice)

    if problems:
        return rows, "; ".join(problems)

    minutes = _verified_minutes(config)
    originally = set(rows)
    for key, group in grouped.items():
        stamps = [notice["source_message_time"] for notice in group]
        if len(stamps) != len(set(stamps)):
            return rows, "notices for %s share a source time, so the newer one cannot be chosen" % key
        ordered = sorted(group, key=lambda notice: datetime.fromisoformat(notice["source_message_time"]))
        current = rows.get(key)
        for notice in ordered:
            stamp = notice["source_message_time"]
            if current is not None and _compare_time(stamp, current["as_of"]) < 0:
                continue
            if current is not None and _compare_time(stamp, current["as_of"]) == 0:
                return rows, "notice for %s ties the record it would replace" % key
            if key not in originally and _compare_time(stamp, generated) < 0:
                return rows, "notice for %s is older than the snapshot and the snapshot does not list it" % key
            if notice["notice"] == "cancelled":
                rows.pop(key, None)
                current = None
                continue
            end = _add_minutes(notice["time"], minutes) if minutes else None
            if minutes and end is None:
                return rows, "verified duration for %s does not fit in the service date" % key
            rows[key] = {
                "reservation_id": notice["reservation_id"],
                "provider": notice["provider"],
                "start": notice["time"],
                "end": end,
                "party": notice.get("party"),
                "guest": notice.get("guest") or "",
                "source": notice.get("source") or "notice",
                "duration_known": end is not None,
                "as_of": stamp,
            }
            current = rows[key]
    return rows, ""


def _slot_is_clear(moment: str, rows: dict) -> bool:
    for row in rows.values():
        if row.get("end") and _inside(moment, row["start"], row["end"]):
            return False
        if not row.get("duration_known") and row["start"] <= moment:
            return False
    return True


def _uncertain_ids(moment: str, rows: dict) -> list:
    found = []
    for row in rows.values():
        if not row.get("duration_known") and row["start"] <= moment:
            found.append(row["reservation_id"])
    return sorted(set(found))


def _hold_reason(item: dict, time: str) -> str:
    """Why a request that is not waiting for approval cannot take one."""
    availability = item.get("availability") or {}
    if item["status"] != "needs_staff_review" or not availability:
        return "this request is not waiting for booking approval"
    if availability.get("blocked_reason"):
        return "held for staff review: " + availability["blocked_reason"]
    for slot in availability.get("withheld_slots") or []:
        if slot.get("time") == time and slot.get("uncertain_reservation_ids"):
            return "held for staff review: %s is withheld because %s have a clock time and no verified duration" % (
                time,
                ", ".join(slot["uncertain_reservation_ids"]),
            )
    conflicts = [row["reservation_id"] for row in availability.get("conflicts") or []]
    if conflicts:
        return "held for staff review: the requested time conflicts with " + ", ".join(conflicts)
    uncertain = availability.get("uncertain_reservation_ids") or []
    if uncertain:
        return "held for staff review: %s have a clock time and no verified duration" % ", ".join(uncertain)
    for slot in availability.get("slots_above_party_max") or []:
        if slot.get("time") == time:
            return "held for staff review: a party of %s is above the maximum of %s for %s" % (
                item.get("party"),
                slot.get("party_max"),
                time,
            )
    if not item.get("offered"):
        return "held for staff review: no slot was offered; the requested time is " + str(
            availability.get("requested_slot") or "not available"
        )
    return "this request is not waiting for booking approval"


def approve(
    store: Store,
    request_id: str,
    service_date: str,
    time: str,
    party: int,
    config: dict,
    snapshot: dict,
) -> dict:
    """Record the owner's decision after checking availability again.

    The offered list a person saw may be older than the notice feed. The
    request is checked once more against the snapshot and every notice
    accepted so far, and the slot must still be offered by that result.
    """
    item = _require(store, request_id)
    if item["status"] not in ("awaiting_staff_booking_approval", "needs_staff_review"):
        raise WorkflowError(_hold_reason(item, time))
    if item["classification"] != "direct_reservation" or item["missing"]:
        raise WorkflowError(_hold_reason(item, time))
    before = [dict(slot) for slot in item["offered"]]
    _check_into(store, item, snapshot, config)
    if item["status"] != "awaiting_staff_booking_approval":
        store.save()
        raise WorkflowError(_hold_reason(item, time))
    match = None
    for slot in item["offered"]:
        if slot["date"] == service_date and slot["time"] == time and slot["party"] == party:
            match = slot
    if match is None:
        store.save()
        if any(slot["date"] == service_date and slot["time"] == time and slot["party"] == party for slot in before):
            raise WorkflowError(
                "%s was offered earlier but is not offered by the current notice feed" % time
            )
        raise WorkflowError("that slot was not one of the offered times")
    text = _confirmation_text(config, service_date, time, party, "{reference}")
    item["approval"] = {
        "action": "write-and-confirm",
        "service_date": service_date,
        "time": time,
        "party": party,
        "at": _now(),
        "rechecked_against": {
            "snapshot_generated_at": snapshot.get("generated_at"),
            "notices_accepted": len(store.data["notices"]),
        },
        "caller_authenticated": False,
    }
    item["authorized_text"] = text
    item["status"] = "booking_write_pending"
    item["history"].append(
        _history("command", "approved", "%s %s party %s" % (service_date, time, party))
    )
    store.save()
    shown = dict(_public_request(item))
    shown["checks"] = {
        "stage": True,
        "offered_slot": True,
        "notice_feed_rechecked": True,
        "caller_authenticated": False,
        "booking_system_read": False,
    }
    shown["next"] = (
        "Enter this in the existing booking system, then record its reference locally. "
        "No guest message has been sent, and no booking API was called."
    )
    shown["confirmation_template"] = text
    return shown


def attach_reference(store: Store, request_id: str, reference: str, snapshot: dict) -> dict:
    item = _require(store, request_id)
    if item["status"] != "booking_write_pending":
        raise WorkflowError("a reference is only accepted after approval and before confirmation")
    if not _REF.match(reference):
        raise WorkflowError("reference does not match the expected pattern")
    for other in store.data["requests"]:
        if other["id"] != item["id"] and other.get("booking_reference") == reference:
            raise WorkflowError("that reference is already attached to another request in this local store")
    for booking in snapshot["bookings"]:
        if booking["reservation_id"] == reference:
            raise WorkflowError("that reference is already in the local snapshot")
    for notice in store.data["notices"]:
        if notice["reservation_id"] == reference and notice["notice"] == "cancelled":
            raise WorkflowError("that reference was cancelled in the local notice feed")
    item["booking_reference"] = reference
    item["service_date"] = item["approval"]["service_date"]
    item["time"] = item["approval"]["time"]
    item["party"] = item["approval"]["party"]
    item["authorized_text"] = _confirmation_text(
        {"restaurant": item["restaurant"]},
        item["service_date"],
        item["time"],
        item["party"],
        reference,
    )
    item["status"] = "reference_recorded_locally"
    item["history"].append(
        _history("command", "reference_recorded_locally", reference + " not read from a booking system")
    )
    store.save()
    shown = _public_request(item)
    shown["checks"] = {
        "pattern": True,
        "local_duplicate": True,
        "caller_authenticated": False,
        "booking_system_read": False,
    }
    return shown


def confirm(store: Store, request_id: str) -> dict:
    item = _require(store, request_id)
    if item["status"] == "guest_confirmation_sent" and item.get("outbound"):
        return {"duplicate": True, "request": _public_request(item)}
    if item["status"] != "reference_recorded_locally" or not item.get("booking_reference"):
        raise WorkflowError("confirmation waits for a locally recorded reference")
    if not item.get("approval") or item["approval"].get("action") != "write-and-confirm":
        raise WorkflowError("the approval did not include the confirmation")
    expected = _confirmation_text(
        {"restaurant": item["restaurant"]},
        item["approval"]["service_date"],
        item["approval"]["time"],
        item["approval"]["party"],
        item["booking_reference"],
    )
    if item["authorized_text"] != expected:
        raise WorkflowError("stored confirmation does not match the approved booking")
    outbound_id = "simulated-" + item["id"]
    item["outbound"] = {
        "live": False,
        "channel": item["channel"],
        "thread_id": item["thread_id"],
        "provider_message_id": outbound_id,
        "text": expected,
        "result": "simulated",
    }
    item["status"] = "guest_confirmation_sent"
    item["history"].append(_history("guest-sender", "confirmation_simulated", outbound_id))
    store.save()
    return {"duplicate": False, "request": _public_request(item)}


def event_questions(store: Store, request_id: str, questions: list, config: dict) -> dict:
    item = _require(store, request_id)
    if item["classification"] != "event_inquiry":
        raise WorkflowError("questions are for an event inquiry")
    if item["status"] not in ("awaiting_staff_questions", "event_reply_approval"):
        raise WorkflowError("this inquiry is not waiting for staff questions")
    cleaned = [question.strip() for question in questions if question.strip()]
    if not cleaned:
        raise WorkflowError("staff have to name the questions")
    lines = [
        "Hello,",
        "",
        "Thank you for asking about an event at %s." % config["restaurant"],
        "Could you tell us:",
    ]
    for question in cleaned:
        lines.append("- " + question)
    item["questions"] = cleaned
    item["authorized_text"] = "\n".join(lines)
    item["status"] = "event_reply_approval"
    item["history"].append(_history("owner", "questions", "; ".join(cleaned)))
    store.save()
    shown = _public_request(item)
    shown["draft"] = item["authorized_text"]
    return shown


def event_send(store: Store, request_id: str, follow_up_due: str) -> dict:
    item = _require(store, request_id)
    if item["status"] != "event_reply_approval" or not item.get("authorized_text"):
        raise WorkflowError("there is no approved event draft to send")
    if not valid_service_date(follow_up_due):
        raise WorkflowError("follow-up due date must be a real YYYY-MM-DD date")
    outbound_id = "simulated-event-" + item["id"]
    item["outbound"] = {
        "live": False,
        "channel": item["channel"],
        "thread_id": item["thread_id"],
        "provider_message_id": outbound_id,
        "text": item["authorized_text"],
        "result": "simulated",
    }
    item["follow_up_due"] = follow_up_due
    item["status"] = "follow_up_due"
    item["history"].append(_history("guest-sender", "event_reply_simulated", outbound_id))
    store.save()
    return _public_request(item)


def ordered_rows(store: Store, snapshot: dict, service_date: str, config: dict | None = None) -> dict:
    """Reconciled rows, or a refusal. An export never prints a feed it could not order."""
    rows, blocked = reconcile(store, snapshot, service_date, config)
    if blocked:
        raise WorkflowError("notice feed for %s cannot be ordered: %s" % (service_date, blocked))
    return rows


def confirmed_rows(store: Store, snapshot: dict, service_date: str, config: dict | None = None) -> list:
    """Staff list for one date. Snapshot and notices are reconciled by timestamp."""
    rows = ordered_rows(store, snapshot, service_date, config)
    listed = {}
    for row in rows.values():
        listed[row["provider"] + ":" + row["reservation_id"]] = {
            "reservation_id": row["reservation_id"],
            "time": row["start"],
            "party": row["party"],
            "guest": row["guest"],
            "source": row["source"],
            "duration_known": row["duration_known"],
        }
    for item in store.data["requests"]:
        reference = item.get("booking_reference")
        if not reference or item["service_date"] != service_date:
            continue
        if item["status"] not in ("reference_recorded_locally", "guest_confirmation_sent"):
            continue
        listed["local:" + reference] = {
            "reservation_id": reference,
            "time": item["time"],
            "party": item["party"],
            "guest": item.get("guest_name", ""),
            "source": "local-reference",
            "duration_known": False,
        }
    return [listed[key] for key in sorted(listed)]


def pending_requests(store: Store, service_date: str) -> tuple:
    """Direct requests for one service date. Others are counted and left out."""
    listed = []
    omitted = 0
    for item in store.data["requests"]:
        if item["classification"] != "direct_reservation":
            continue
        if item["status"] in ("guest_confirmation_sent", "declined", "cancelled", "expired"):
            continue
        if item.get("service_date") == service_date:
            listed.append(item)
        else:
            omitted += 1
    return listed, omitted


def calendar_plan(store: Store, snapshot: dict, service_date: str, config: dict | None = None) -> tuple:
    """Events with a known start and end, and rows omitted because duration is unknown.

    A cancellation drops the matching provider row. A notice without a verified
    duration is named and left out. It is not given a one-minute length.
    """
    rows = ordered_rows(store, snapshot, service_date, config)
    windows = {}
    omitted = {}
    for key, row in rows.items():
        if row.get("duration_known") and row.get("end"):
            windows[key] = row
        else:
            omitted[key] = "notice has a clock time and no duration"
    for item in store.data["requests"]:
        reference = item.get("booking_reference")
        if not reference or item.get("service_date") != service_date:
            continue
        if item["status"] not in ("reference_recorded_locally", "guest_confirmation_sent"):
            continue
        local_key = "local:" + reference
        if local_key not in windows:
            omitted[local_key] = "recorded reference has a clock time and no duration"
    included = [windows[key] for key in sorted(windows)]
    omitted_rows = []
    for key in sorted(omitted):
        reservation_id = key.split(":", 1)[1] if ":" in key else key
        omitted_rows.append({"reservation_id": reservation_id, "reason": omitted[key]})
    return included, omitted_rows


def _confirmation_text(config: dict, service_date: str, time: str, party: int, reference: str) -> str:
    restaurant = config["restaurant"]
    return (
        "%s: staff recorded reference %s for %s people on %s at %s. "
        "This reference was checked locally and was not read back from a booking system. "
        "This send is simulated and was not delivered to a guest."
        % (restaurant, reference, party, service_date, time)
    )


def _require(store: Store, request_id: str) -> dict:
    item = store.request_by_id(request_id)
    if item is None:
        raise WorkflowError("unknown request")
    return item
