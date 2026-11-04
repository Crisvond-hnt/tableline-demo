"""One-page daily list. Stdlib only, no PDF package."""

from __future__ import annotations

from datetime import datetime, timezone

from integrations.store import Store
from integrations.workflow import confirmed_rows, pending_requests


def build_pdf(store: Store, snapshot: dict, config: dict, service_date: str) -> bytes:
    generated = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    lines = [
        "DAILY RESERVATION LIST",
        config["restaurant"] + "  |  SYNTHETIC",
        "Service date: " + service_date,
        "Timezone: " + config["timezone"],
        "Generated: " + generated,
        "Availability source: " + snapshot["source"],
        "Snapshot generated: " + snapshot["generated_at"],
        "This list is derived from the snapshot and local records. It is not a live sync.",
        "",
        "CONFIRMED",
    ]
    rows = confirmed_rows(store, snapshot, service_date, config)
    if not rows:
        lines.append("(none)")
    for row in rows:
        lines.append(
            "%s  %s  party %s  %s  [%s]%s"
            % (
                row["time"],
                row["reservation_id"],
                row["party"],
                row["guest"] or "-",
                row["source"],
                "" if row.get("duration_known") else "  duration unknown",
            )
        )
    lines.extend(["", "PENDING REQUESTS FOR " + service_date])
    pending, omitted_pending = pending_requests(store, service_date)
    if not pending:
        lines.append("(none)")
    for item in pending:
        lines.append(
            "%s  %s  %s  party %s  %s"
            % (
                item["status"],
                item["id"],
                item.get("time") or "-",
                item.get("party") or "-",
                item.get("guest_name") or "-",
            )
        )
    lines.append("Pending on another date or with no date, not listed: %s" % omitted_pending)
    lines.extend(["", "EVENT INQUIRIES"])
    events = [item for item in store.data["requests"] if item["classification"] == "event_inquiry"]
    if not events:
        lines.append("(none)")
    for item in events:
        due = item.get("follow_up_due") or "no due date"
        lines.append("%s  %s  follow-up %s" % (item["status"], item["id"], due))
    lines.extend(["", "NOTICES HELD FOR STAFF: %s" % len(store.data["review"])])
    return _pdf(lines)


def _pdf(lines: list) -> bytes:
    pages = [lines[index : index + 46] for index in range(0, len(lines), 46)] or [[]]
    objects = []
    kids = []

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    font_id = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>")
    content_ids = []
    for page_lines in pages:
        content_ids.append(add(_stream(_page_commands(page_lines))))
    for content_id in content_ids:
        page_id = add(
            (
                "<< /Type /Page /Parent PAGES 0 R /Resources << /Font << /F1 %d 0 R >> >> "
                "/MediaBox [0 0 612 792] /Contents %d 0 R >>"
                % (font_id, content_id)
            ).encode("ascii")
        )
        kids.append(page_id)
    kids_text = " ".join("%d 0 R" % kid for kid in kids)
    pages_id = add(("<< /Type /Pages /Count %d /Kids [%s] >>" % (len(kids), kids_text)).encode("ascii"))
    # Parent references were written as the literal token PAGES. Rewrite those page objects.
    for index, page_id in enumerate(kids):
        objects[page_id - 1] = objects[page_id - 1].replace(b"Parent PAGES 0 R", b"Parent %d 0 R" % pages_id)
    catalog_id = add(("<< /Type /Catalog /Pages %d 0 R >>" % pages_id).encode("ascii"))
    return _serialize(objects, catalog_id)


def _page_commands(lines: list) -> bytes:
    commands = ["BT", "/F1 10 Tf", "48 760 Td", "14 TL"]
    for line in lines:
        commands.append("(" + _escape(line) + ") '")
    commands.append("ET")
    return ("\n".join(commands) + "\n").encode("latin-1")


def _escape(line: str) -> str:
    ascii_line = line.encode("latin-1", errors="replace").decode("latin-1")
    return ascii_line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _stream(payload: bytes) -> bytes:
    return b"<< /Length %d >>\nstream\n" % len(payload) + payload + b"endstream"


def _serialize(objects: list, catalog_id: int) -> bytes:
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(b"%d 0 obj\n" % number)
        output.extend(body)
        output.extend(b"\nendobj\n")
    xref = len(output)
    output.extend(("xref\n0 %d\n" % (len(objects) + 1)).encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(("%010d 00000 n \n" % offset).encode("ascii"))
    output.extend(
        (
            "trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n"
            % (len(objects) + 1, catalog_id, xref)
        ).encode("ascii")
    )
    return bytes(output)
