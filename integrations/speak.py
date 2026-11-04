"""The sentence the room hears.

The command still returns the record. This is the only part that should
be posted. It names reservation ids, never another guest, and it does
not mention a command, a file, or a timestamp.
"""

from __future__ import annotations


def speak(command: str, result) -> str:
    if command == "demo" and isinstance(result, dict):
        return _demo(result)
    if command == "check" and isinstance(result, dict):
        return _check(result)
    if command == "approve" and isinstance(result, dict):
        return _approve(result)
    if command == "reference" and isinstance(result, dict):
        return _reference(result)
    if command == "confirm" and isinstance(result, dict):
        return _confirm(result)
    if command == "review" and isinstance(result, dict):
        return _review(result)
    if command == "intake" and isinstance(result, dict):
        return _intake(result)
    if command in ("pdf", "ics") and isinstance(result, dict):
        return _export(command, result)
    if command == "ingest":
        return "I've read the notices for tonight. Ask me what I held back if you want the ones I didn't trust."
    if command == "ingest-mail":
        return "I've read that notice. It stays out of the book if something on it didn't check out."
    if command == "configure":
        return "The house rules we haven't been told are still marked unknown. I won't invent them."
    return "That's done. I didn't write a booking, and I didn't send anything to a guest."


def speak_error(code: str) -> str:
    text = code or "that didn't go through"
    lower = text.lower()
    if "not waiting for booking approval" in lower or "no slot was offered" in lower:
        return "I can't approve that. It isn't one of the times I can offer."
    if "withheld" in lower or "no verified duration" in lower:
        return "I can't approve that time. Another table starts earlier and I don't know when it finishes, so I'm not calling the night free."
    if "was offered earlier" in lower:
        return "That time was free a moment ago. A newer notice covers it, so I won't approve it."
    if "not one of the offered" in lower:
        return "That isn't a time I offered. I won't approve it."
    if "already in the local snapshot" in lower or "already in this local" in lower:
        return "That number is already on the book. I won't write it down again."
    if "waits for a locally recorded reference" in lower:
        return "I won't reply to the guest yet. We need a reference written down first."
    if "cancelled in the local notice" in lower:
        return "That reservation was cancelled in the notices I have. I won't use it."
    if "missing " in lower:
        return "I don't have enough to check a table. I still need " + text.split("missing ", 1)[-1] + "."
    if "not a real" in lower or "not hh:mm" in lower:
        return "That date or time doesn't look real, so I left it for you."
    return "I didn't do that. " + text[:1].upper() + text[1:] + "."


def _clock(value: str) -> str:
    if not isinstance(value, str) or len(value) < 4 or ":" not in value:
        return str(value)
    hour, minute = value.split(":", 1)
    try:
        number = int(hour)
    except ValueError:
        return value
    number = number % 12 or 12
    if minute == "00":
        return "%s o'clock" % number
    return "%s:%s" % (number, minute)


def _demo(result: dict) -> str:
    conflicts = result.get("conflicts") or []
    conflict = conflicts[0] if conflicts else "another booking"
    withheld = []
    for slot in result.get("withheld_slots") or []:
        if slot.get("time") == "21:30":
            withheld = slot.get("uncertain_reservation_ids") or []
    if len(withheld) >= 2:
        later = "%s and %s start earlier and I don't know when they finish" % (withheld[0], withheld[1])
    elif withheld:
        later = "%s starts earlier and I don't know when it finishes" % withheld[0]
    else:
        later = "I don't know when the other tables finish"
    offered = result.get("offered") or []
    if offered:
        ending = "I can offer " + ", ".join(_clock(slot.get("time", "")) for slot in offered) + "."
    else:
        ending = "I can't give her 9:30 either, because %s." % later
    return (
        "Mara wants four people at 8 o'clock. That's taken. %s is in from 7:30 to 9. %s "
        "Nothing has been written, and I haven't told Mara. This is the practice sheet, not the live book."
        % (conflict, ending[:1].upper() + ending[1:])
    )


def _check(result: dict) -> str:
    name = result.get("guest_name") or "They"
    party = result.get("party") or "a party"
    when = _clock(result.get("time") or "")
    availability = result.get("availability") or {}
    conflicts = [row.get("reservation_id") for row in availability.get("conflicts") or [] if row.get("reservation_id")]
    offered = result.get("offered") or []
    if conflicts:
        taken = "%s is taken by %s." % (when, conflicts[0])
    else:
        taken = ""
    if offered:
        times = ", ".join(_clock(slot.get("time", "")) for slot in offered)
        return "%s asked for %s at %s. %s I can offer %s. Nothing is written yet." % (name, party, when, taken, times)
    return (
        "%s asked for %s at %s. %s I don't have a time to offer. Nothing is written yet."
        % (name, party, when, taken)
    ).replace("  ", " ")


def _approve(result: dict) -> str:
    approval = result.get("approval") or {}
    return (
        "All right. %s for %s on the 14th is noted, because you asked for it and it's still open. "
        "The book itself is unchanged. When you've entered it there, tell me the reference."
        % (_clock(approval.get("time") or ""), approval.get("party") or "the party")
    )


def _reference(result: dict) -> str:
    reference = result.get("booking_reference") or "that number"
    return (
        "I've written %s down in this room. I didn't read it back from the reservation system, so this is not a confirmation yet."
        % reference
    )


def _confirm(result: dict) -> str:
    request = result.get("request") or result
    outbound = request.get("outbound") or {}
    if outbound.get("result") == "simulated" or request.get("status") == "guest_confirmation_sent":
        return "The reply to the guest is saved here as a draft. It was not sent."
    return "I saved the reply here. It was not sent."


def _review(result: dict) -> str:
    held = result.get("held") or []
    if not held:
        return "Nothing is waiting. Everything I read was clear enough to keep."
    reasons = []
    for item in held:
        reason = (item.get("reason") or "").lower()
        if "sender" in reason:
            reasons.append("one notice came from the wrong sender")
        elif "missing reservation" in reason or "missing the reservation" in reason:
            reasons.append("one was missing the reservation")
        elif "party" in reason:
            reasons.append("one booking had no party size")
        elif "unrecognized" in reason or "kind" in reason:
            reasons.append("one wasn't a new booking, a change, or a cancellation")
        else:
            reasons.append("one needs you to look at it")
    unique = []
    for reason in reasons:
        if reason not in unique:
            unique.append(reason)
    count = result.get("count") if isinstance(result.get("count"), int) else len(held)
    return (
        "%s things need a person before they belong in the night. %s. None of them went into the book."
        % (count, "; ".join(unique))
    )


def _intake(result: dict) -> str:
    request = result.get("request") or {}
    if result.get("duplicate"):
        return "I've already got that message. I won't start a second one."
    name = request.get("guest_name") or "Someone"
    if request.get("classification") == "event_inquiry":
        return "%s is asking about an event, not a table tonight. I'll wait for you to say what we still need to ask." % name
    return "I've got %s's message. Ask me if we can take it." % name


def _export(command: str, result: dict) -> str:
    included = result.get("included") or []
    omitted = result.get("omitted") or []
    names = ", ".join(row if isinstance(row, str) else row.get("reservation_id", "") for row in included)
    names = names or "the tables with a start and a finish"
    left = len(omitted)
    kind = "The evening list" if command == "pdf" else "The calendar file"
    if left:
        return "%s is ready. %s are on it. %s more don't have a finish time, so I left them off." % (kind, names, left)
    return "%s is ready. %s are on it." % (kind, names)
