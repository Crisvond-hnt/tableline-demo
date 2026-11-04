"""ICS for rows that have a start and an end. Unknown durations become COMMENT lines."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from integrations.workflow import calendar_plan


def build_ics(store, snapshot: dict, config: dict, service_date: str) -> dict:
    included, omitted = calendar_plan(store, snapshot, service_date, config)
    zone = ZoneInfo(config["timezone"])
    stamp = datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Tableline//synthetic snapshot//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "COMMENT:Derived from the synthetic snapshot and local records. Not a live sync.",
        "COMMENT:Timezone %s converted to UTC." % config["timezone"],
        "COMMENT:Snapshot generated %s." % snapshot["generated_at"],
    ]
    if not omitted:
        lines.append("COMMENT:No rows were omitted for an unknown duration.")
    for row in omitted:
        lines.append("COMMENT:Omitted %s because %s." % (row["reservation_id"], row["reason"]))
    for row in included:
        lines.extend(
            [
                "BEGIN:VEVENT",
                "UID:tableline-%s-%s-%s@northline.example.test"
                % (row.get("provider") or "record", row["reservation_id"], service_date),
                "DTSTAMP:" + stamp,
                "DTSTART:" + _utc(service_date, row["start"], zone),
                "DTEND:" + _utc(service_date, row["end"], zone),
                "SUMMARY:%s party %s" % (row["reservation_id"], row["party"]),
                "DESCRIPTION:Source %s. Synthetic record." % row["source"],
                "END:VEVENT",
            ]
        )
    lines.append("END:VCALENDAR")
    body = "\r\n".join(lines) + "\r\n"
    return {"body": body, "included": included, "omitted": omitted}


def _utc(service_date: str, clock: str, zone: ZoneInfo) -> str:
    local = datetime.fromisoformat(service_date + "T" + clock).replace(tzinfo=zone)
    return local.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
