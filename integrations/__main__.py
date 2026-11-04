"""CLI for the checks the coordinator runs."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from integrations.calendar import build_ics
from integrations.config import ROOT, classify_rules, config_path, load_config, load_snapshot, validate_config
from integrations.mailbox import ingest_dir
from integrations.mailbox import ingest_file as ingest_mail_file
from integrations.pdf import build_pdf
from integrations.store import Store, store_path
from integrations.thefork import ingest_dir as ingest_thefork
from integrations.speak import speak, speak_error
from integrations.workflow import (
    WorkflowError,
    approve,
    attach_reference,
    check,
    confirm,
    event_questions,
    event_send,
    intake,
)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Tableline adapters")
    sub = parser.add_subparsers(dest="command", required=True)
    mail_parser = sub.add_parser("ingest-mail")
    mail_parser.add_argument("path", nargs="?", type=Path, help="one .eml file or a folder of them; default fixtures/emails")
    sub.add_parser("ingest")
    sub.add_parser("review")
    sub.add_parser("demo")
    configure_parser = sub.add_parser("configure")
    configure_parser.add_argument("path", nargs="?", type=Path)
    intake_parser = sub.add_parser("intake")
    intake_parser.add_argument("fixture", type=Path)
    check_parser = sub.add_parser("check")
    check_parser.add_argument("request_id")
    approve_parser = sub.add_parser("approve")
    approve_parser.add_argument("request_id")
    approve_parser.add_argument("--date", required=True)
    approve_parser.add_argument("--time", required=True)
    approve_parser.add_argument("--party", required=True, type=int)
    reference_parser = sub.add_parser("reference")
    reference_parser.add_argument("request_id")
    reference_parser.add_argument("reference")
    confirm_parser = sub.add_parser("confirm")
    confirm_parser.add_argument("request_id")
    questions = sub.add_parser("event-questions")
    questions.add_argument("request_id")
    questions.add_argument("--ask", action="append", required=True)
    send = sub.add_parser("event-send")
    send.add_argument("request_id")
    send.add_argument("--due", required=True)
    pdf_parser = sub.add_parser("pdf")
    pdf_parser.add_argument("--date", required=True)
    pdf_parser.add_argument("--out", type=Path, required=True)
    ics_parser = sub.add_parser("ics")
    ics_parser.add_argument("--date", required=True)
    ics_parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        payload = _run(args)
    except WorkflowError as error:
        print(json.dumps({"ok": False, "error": error.code, "say": speak_error(error.code)}))
        return 1
    print(json.dumps({"ok": True, "say": speak(args.command, payload), "result": payload}, indent=2))
    return 0


def _demo(config: dict, snapshot: dict) -> dict:
    """Run the fixture night in a temporary ledger and discard it."""
    holding = tempfile.TemporaryDirectory()
    store = Store(Path(holding.name) / "store.json")
    try:
        ingest_dir(store, ROOT / "fixtures" / "emails", config)
        ingest_thefork(store, ROOT / "fixtures" / "thefork")
        created = intake(
            store,
            json.loads((ROOT / "fixtures" / "messages" / "instagram-party-of-four.json").read_text()),
            config,
            snapshot,
        )
        checked = check(store, created["request"]["id"], snapshot, config)
        try:
            approve(store, created["request"]["id"], "2026-11-14", "21:30", 4, config, snapshot)
            approval = "accepted"
        except WorkflowError as error:
            approval = error.code
        document = build_pdf(store, snapshot, config, "2026-11-14")
        calendar = build_ics(store, snapshot, config, "2026-11-14")
        return {
            "ledger": "temporary and discarded",
            "live": False,
            "snapshot_generated_at": snapshot["generated_at"],
            "request_id": created["request"]["id"],
            "request": "%s people at %s on %s" % (
                created["request"]["party"],
                created["request"]["time"],
                created["request"]["service_date"],
            ),
            "status": checked["status"],
            "conflicts": [row["reservation_id"] for row in checked["availability"]["conflicts"]],
            "offered": checked["offered"],
            "withheld_slots": checked["availability"]["withheld_slots"],
            "uncertain_reservation_ids": checked["availability"]["uncertain_reservation_ids"],
            "duration_rule": checked["availability"]["duration_rule"],
            "approve_21_30": approval,
            "held_for_review": len(store.data["review"]),
            "pdf_bytes": len(document),
            "ics_included": [row["reservation_id"] for row in calendar["included"]],
            "ics_omitted": calendar["omitted"],
        }
    finally:
        holding.cleanup()


def _run(args):
    config = load_config()
    snapshot = load_snapshot()
    store = Store(store_path())
    if args.command == "configure":
        path = args.path or config_path()
        data = json.loads(path.read_text())
        errors = validate_config(data)
        if errors:
            raise WorkflowError("; ".join(errors))
        return {"path": str(path), "rules": classify_rules(data)}
    if args.command == "demo":
        return _demo(config, snapshot)
    if args.command == "ingest-mail":
        target = args.path or ROOT / "fixtures" / "emails"
        if target.is_file():
            return [ingest_mail_file(store, target, config)]
        return ingest_dir(store, target, config)
    if args.command == "ingest":
        return {
            "umai_email": ingest_dir(store, ROOT / "fixtures" / "emails", config),
            "thefork": ingest_thefork(store, ROOT / "fixtures" / "thefork"),
        }
    if args.command == "review":
        return {
            "count": len(store.data["review"]),
            "held": store.data["review"],
            "note": (
                "Each item is a file or event that was not accepted. Nothing here is marked seen, "
                "so a corrected copy can be ingested again."
            ),
        }
    if args.command == "intake":
        message = json.loads(args.fixture.read_text())
        return intake(store, message, config, snapshot)
    if args.command == "check":
        return check(store, args.request_id, snapshot, config)
    if args.command == "approve":
        return approve(store, args.request_id, args.date, args.time, args.party, config, snapshot)
    if args.command == "reference":
        return attach_reference(store, args.request_id, args.reference, snapshot)
    if args.command == "confirm":
        return confirm(store, args.request_id)
    if args.command == "event-questions":
        return event_questions(store, args.request_id, args.ask, config)
    if args.command == "event-send":
        return event_send(store, args.request_id, args.due)
    if args.command == "pdf":
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_bytes(build_pdf(store, snapshot, config, args.date))
        return {"path": str(args.out), "bytes": args.out.stat().st_size}
    if args.command == "ics":
        built = build_ics(store, snapshot, config, args.date)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_bytes(built["body"].encode("utf-8"))
        return {
            "path": str(args.out),
            "included": [row["reservation_id"] for row in built["included"]],
            "omitted": built["omitted"],
        }
    raise WorkflowError("unknown command")


if __name__ == "__main__":
    sys.exit(main())
