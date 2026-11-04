"""Checks for the synthetic Northline night."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from integrations.config import load_config, load_snapshot  # noqa: E402
from integrations.mailbox import ingest_dir, ingest_file  # noqa: E402
from integrations.pdf import build_pdf  # noqa: E402
from integrations.store import Store  # noqa: E402
from integrations.workflow import (  # noqa: E402
    WorkflowError,
    approve,
    attach_reference,
    check,
    confirm,
    event_questions,
    event_send,
    intake,
)


def _message(name: str) -> dict:
    return json.loads((ROOT / "fixtures" / "messages" / name).read_text())


class TablelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temporary.name) / "store.json")
        self.config = load_config(ROOT)
        self.snapshot = load_snapshot(ROOT)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_notice_feed_is_idempotent_and_picky(self) -> None:
        results = ingest_dir(self.store, ROOT / "fixtures" / "emails", self.config)
        self.assertTrue(results[3]["duplicate"])
        notices = self.store.data["notices"]
        self.assertEqual(len(notices), 3)
        edited = [notice for notice in notices if notice["reservation_id"] == "NL-1042"][-1]
        self.assertEqual(edited["time"], "19:00")
        self.assertEqual(edited["notice"], "updated")
        reasons = [item["reason"] for item in self.store.data["review"]]
        self.assertIn("sender domain is not the configured notice domain", reasons)
        self.assertTrue(any("missing" in reason for reason in reasons))
        self.assertNotIn("Should Not Import", json.dumps(self.store.data["notices"]))

    def test_direct_request_conflict_hides_the_other_guest(self) -> None:
        ingest_dir(self.store, ROOT / "fixtures" / "emails", self.config)
        created = intake(self.store, _message("instagram-party-of-four.json"), self.config, self.snapshot)
        request_id = created["request"]["id"]
        checked = check(self.store, request_id, self.snapshot)
        blob = json.dumps(checked)
        self.assertNotIn("Jonah Hale", blob)
        self.assertNotIn("Noor Patel", blob)
        self.assertEqual(checked["availability"]["live"], False)
        self.assertEqual(checked["availability"]["conflicts"][0]["reservation_id"], "NL-0881")
        self.assertEqual(checked["offered"], [])
        self.assertEqual(checked["status"], "needs_staff_review")
        self.assertIn("NL-1042", checked["availability"]["uncertain_reservation_ids"])
        self.assertEqual(checked["availability"]["duration_rule"], "unknown")
        duplicate = intake(self.store, _message("instagram-duplicate.json"), self.config, self.snapshot)
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(len(self.store.request_by_id(request_id)["message_ids"]), 1)

    def test_approval_reference_and_confirmation_order(self) -> None:
        ingest_file(self.store, ROOT / "fixtures" / "emails" / "03-cancelled-nl-0770.eml", self.config)
        created = intake(self.store, _message("instagram-party-of-four.json"), self.config, self.snapshot)
        request_id = created["request"]["id"]
        check(self.store, request_id, self.snapshot)
        follow = intake(self.store, _message("instagram-follow-up.json"), self.config, self.snapshot)
        self.assertEqual(follow["request"]["time"], "21:30")
        self.assertEqual(follow["request"]["status"], "awaiting_staff_booking_approval")
        with self.assertRaises(WorkflowError) as blocked:
            approve(self.store, request_id, "2026-11-14", "20:00", 4, self.config, self.snapshot)
        self.assertIn("not one of the offered", blocked.exception.code)
        approved = approve(self.store, request_id, "2026-11-14", "21:30", 4, self.config, self.snapshot)
        self.assertTrue(approved["checks"]["notice_feed_rechecked"])
        self.assertEqual(approved["approval"]["rechecked_against"]["notices_accepted"], 1)
        with self.assertRaises(WorkflowError):
            confirm(self.store, request_id)
        with self.assertRaises(WorkflowError) as reused:
            attach_reference(self.store, request_id, "NL-0881", self.snapshot)
        self.assertIn("local snapshot", reused.exception.code)
        attached = attach_reference(self.store, request_id, "NL-2044", self.snapshot)
        self.assertEqual(attached["status"], "reference_recorded_locally")
        self.assertFalse(attached["checks"]["booking_system_read"])
        self.assertFalse(attached["checks"]["caller_authenticated"])
        self.assertNotIn("reference_verified", json.dumps(attached["history"]))
        sent = confirm(self.store, request_id)
        self.assertEqual(sent["request"]["outbound"]["result"], "simulated")
        self.assertEqual(sent["request"]["outbound"]["provider_message_id"], "simulated-" + request_id)
        self.assertIn("not read back from a booking system", sent["request"]["outbound"]["text"])
        again = confirm(self.store, request_id)
        self.assertTrue(again["duplicate"])

    def test_incomplete_request_and_event_inquiry(self) -> None:
        incomplete = intake(self.store, _message("instagram-incomplete.json"), self.config, self.snapshot)
        self.assertEqual(incomplete["request"]["status"], "needs_information")
        self.assertIn("party size", incomplete["request"]["missing"])
        event = intake(self.store, _message("email-event.json"), self.config, self.snapshot)
        request_id = event["request"]["id"]
        self.assertEqual(event["request"]["classification"], "event_inquiry")
        self.assertNotEqual(event["request"]["status"], "awaiting_staff_booking_approval")
        with self.assertRaises(WorkflowError):
            event_send(self.store, request_id, "2026-11-18")
        draft = event_questions(
            self.store,
            request_id,
            ["date flexibility", "guest count", "budget range", "requirements"],
            self.config,
        )
        self.assertIn("date flexibility", draft["draft"])
        self.assertIsNone(draft["outbound"])
        sent = event_send(self.store, request_id, "2026-11-18")
        self.assertEqual(sent["status"], "follow_up_due")
        self.assertEqual(sent["follow_up_due"], "2026-11-18")
        self.assertEqual(sent["outbound"]["result"], "simulated")

    def test_pdf_separates_confirmed_pending_and_events(self) -> None:
        ingest_file(self.store, ROOT / "fixtures" / "emails" / "03-cancelled-nl-0770.eml", self.config)
        created = intake(self.store, _message("instagram-party-of-four.json"), self.config, self.snapshot)
        request_id = created["request"]["id"]
        check(self.store, request_id, self.snapshot)
        intake(self.store, _message("instagram-follow-up.json"), self.config, self.snapshot)
        approve(self.store, request_id, "2026-11-14", "21:30", 4, self.config, self.snapshot)
        attach_reference(self.store, request_id, "NL-2044", self.snapshot)
        confirm(self.store, request_id)
        ingest_file(self.store, ROOT / "fixtures" / "emails" / "01-new-nl-1042.eml", self.config)
        ingest_file(self.store, ROOT / "fixtures" / "emails" / "02-edited-nl-1042.eml", self.config)
        intake(self.store, _message("email-event.json"), self.config, self.snapshot)
        intake(self.store, _message("instagram-incomplete.json"), self.config, self.snapshot)
        other_day = {
            "synthetic": True,
            "live": False,
            "channel": "email",
            "thread_id": "mail-thread-other",
            "message_id": "mail-msg-other",
            "received_at": "2026-11-14T18:00:00+00:00",
            "guest_name": "Riley Cho",
            "text": "Please book a table for two on 2026-11-20 at 19:00.",
        }
        intake(self.store, other_day, self.config, self.snapshot)
        document = build_pdf(self.store, self.snapshot, self.config, "2026-11-14")
        self.assertTrue(document.startswith(b"%PDF-1.4"))
        text = document.decode("latin-1", errors="ignore")
        self.assertIn("NL-1042", text)
        self.assertIn("19:00", text)
        self.assertNotIn("NL-0770", text)
        self.assertIn("NL-2044", text)
        self.assertIn("NL-0881", text)
        self.assertIn("EVENT INQUIRIES", text)
        self.assertIn("PENDING REQUESTS FOR 2026-11-14", text)
        self.assertIn("Sam Ibarra", text)
        self.assertNotIn("Riley Cho", text)
        self.assertIn("duration unknown", text)
        self.assertIn("not a live sync", text)
        confirmed_at = text.index("CONFIRMED")
        pending_at = text.index("PENDING REQUESTS FOR 2026-11-14")
        event_at = text.index("EVENT INQUIRIES")
        self.assertLess(confirmed_at, pending_at)
        self.assertLess(pending_at, event_at)
        self.assertIn("Europe/Lisbon", text)

    def test_template_and_cli(self) -> None:
        template = (ROOT / "templates" / "tableline.template.yaml").read_text()
        self.assertNotIn("/Users/", template)
        self.assertNotIn("cursor", template.lower())
        self.assertIn('default: [claude, codex, opencode]', template)
        self.assertIn("addressing: owner-agents", template)
        self.assertIn("auto_approve: false", template)
        self.assertIn("auto_mode: false", template)
        self.assertNotIn("$first", template)
        completed_yaml = subprocess.run(
            [
                "ruby",
                "-ryaml",
                "-e",
                "YAML.load_file(ARGV[0]); puts 'parsed'",
                str(ROOT / "templates" / "tableline.template.yaml"),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed_yaml.returncode, 0, completed_yaml.stderr)
        self.assertIn("parsed", completed_yaml.stdout)
        environment = dict(os.environ)
        environment["TABLELINE_STORE"] = str(Path(self.temporary.name) / "cli.json")
        completed = subprocess.run(
            [sys.executable, "-m", "integrations", "ingest-mail"],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn('"ok": true', completed.stdout)
        demo = subprocess.run(
            [sys.executable, "-m", "integrations", "demo"],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(demo.returncode, 0, demo.stderr)
        payload = json.loads(demo.stdout)
        self.assertEqual(payload["result"]["offered"], [])
        self.assertIn("NL-0881", payload["result"]["conflicts"])
        self.assertEqual(payload["result"]["ledger"], "temporary and discarded")
        self.assertEqual(payload["result"]["snapshot_generated_at"], "2026-11-14T16:00:00+00:00")
        self.assertEqual(payload["result"]["withheld_slots"][0]["time"], "21:30")
        self.assertIn("21:30 is withheld", payload["result"]["approve_21_30"])
        self.assertGreater(payload["result"]["held_for_review"], 0)
        said = payload["say"]
        self.assertIn("8 o'clock", said)
        self.assertIn("NL-0881", said)
        self.assertIn("NL-1042", said)
        self.assertIn("TF-2201", said)
        self.assertNotIn("Jonah", said)
        self.assertNotIn("python", said.lower())
        self.assertNotIn("{", said)
        self.assertFalse((ROOT / "var" / "store.json").exists())

    def test_ledgers_stay_in_the_directory_that_wrote_them(self) -> None:
        other = Store(Path(self.temporary.name) / "other-agent.json")
        intake(self.store, _message("instagram-party-of-four.json"), self.config, self.snapshot)
        self.assertEqual(other.data["requests"], [])
        self.assertEqual(len(self.store.data["requests"]), 1)

    def test_calendar_keeps_known_durations_and_names_the_rest(self) -> None:
        from integrations.calendar import build_ics

        ingest_file(self.store, ROOT / "fixtures" / "emails" / "03-cancelled-nl-0770.eml", self.config)
        created = intake(self.store, _message("instagram-party-of-four.json"), self.config, self.snapshot)
        request_id = created["request"]["id"]
        check(self.store, request_id, self.snapshot, self.config)
        intake(self.store, _message("instagram-follow-up.json"), self.config, self.snapshot)
        approve(self.store, request_id, "2026-11-14", "21:30", 4, self.config, self.snapshot)
        attach_reference(self.store, request_id, "NL-2044", self.snapshot)
        ingest_file(self.store, ROOT / "fixtures" / "emails" / "01-new-nl-1042.eml", self.config)
        ingest_file(self.store, ROOT / "fixtures" / "emails" / "02-edited-nl-1042.eml", self.config)
        built = build_ics(self.store, self.snapshot, self.config, "2026-11-14")
        body = built["body"]
        self.assertTrue(body.startswith("BEGIN:VCALENDAR"))
        self.assertIn("DTSTART:20261114T193000Z", body)
        self.assertIn("DTEND:20261114T210000Z", body)
        self.assertIn("DTEND:20261114T191500Z", body)
        self.assertNotIn("NL-0770", body)
        self.assertNotIn("BEGIN:VEVENT\r\nUID:tableline-NL-1042", body)
        reasons = {row["reservation_id"]: row["reason"] for row in built["omitted"]}
        self.assertEqual(reasons["NL-1042"], "notice has a clock time and no duration")
        self.assertEqual(reasons["NL-2044"], "recorded reference has a clock time and no duration")
        self.assertNotIn("NL-0770", reasons)
        included = {row["reservation_id"] for row in built["included"]}
        self.assertEqual(included, {"NL-0881", "NL-0902"})

    def test_umai_and_thefork_fixtures_share_one_feed(self) -> None:
        from integrations.thefork import ingest_dir as ingest_thefork

        ingest_dir(self.store, ROOT / "fixtures" / "emails", self.config)
        fork = ingest_thefork(self.store, ROOT / "fixtures" / "thefork")
        self.assertTrue(fork[3]["duplicate"])
        providers = {notice["provider"] for notice in self.store.data["notices"]}
        self.assertEqual(providers, {"umai", "thefork"})
        edited = [notice for notice in self.store.data["notices"] if notice["reservation_id"] == "TF-2201"][-1]
        self.assertEqual(edited["time"], "20:15")
        self.assertEqual(edited["source"], "thefork-fixture")
        self.assertIn("api.thefork.io", edited["freshness"])
        self.assertFalse(edited["live"])
        reasons = [item["reason"] for item in self.store.data["review"]]
        self.assertTrue(any("missing party" in reason for reason in reasons))
        self.assertTrue(any("unrecognized notice kind" in reason for reason in reasons))
        self.assertNotIn("TF-2300", json.dumps(self.store.data["notices"]))
        self.assertNotIn("TF-2400", json.dumps(self.store.data["notices"]))
        created = intake(self.store, _message("instagram-party-of-four.json"), self.config, self.snapshot)
        checked = check(self.store, created["request"]["id"], self.snapshot)
        self.assertIn("No mailbox was polled", checked["availability"]["notice_feed"]["freshness"])
        self.assertEqual(
            checked["availability"]["notice_feed"]["latest_source_message_time"],
            "2026-11-14T16:45:00+00:00",
        )
        self.assertEqual(checked["offered"], [])
        self.assertIn("NL-1042", checked["availability"]["uncertain_reservation_ids"])
        withheld = checked["availability"]["withheld_slots"]
        self.assertEqual(withheld[0]["time"], "21:30")
        self.assertIn("NL-1042", withheld[0]["uncertain_reservation_ids"])
        self.assertIn("TF-2201", withheld[0]["uncertain_reservation_ids"])
        sample = [notice for notice in self.store.data["notices"] if notice["reservation_id"] == "NL-1042"][-1]
        self.assertIn("source_message_time", sample)
        self.assertIn("ingested_at", sample)
        self.assertNotIn("received_at", sample)
        self.assertIn("not proof a mailbox received it", sample["freshness"])

    def test_configuration_keeps_unknown_rules_and_rejects_a_live_source(self) -> None:
        from integrations.config import classify_rules, validate_config

        report = classify_rules(self.config)
        self.assertIn("opening_hours", report["unknown"])
        self.assertIn("daily_output", report["unknown"])
        bad = json.loads(json.dumps(self.config))
        bad["rules"]["daily_output"] = "sync"
        bad["rules"]["sources"] = [{"name": "UMAI", "status": "connected"}]
        errors = validate_config(bad)
        self.assertTrue(any("daily_output" in item for item in errors))
        self.assertTrue(any("status" in item for item in errors))

    def test_unknown_duration_does_not_clear_a_later_slot(self) -> None:
        from integrations.events import SCHEMA, record_event
        from integrations.workflow import reconcile

        ingest_file(self.store, ROOT / "fixtures" / "emails" / "03-cancelled-nl-0770.eml", self.config)
        record_event(
            self.store,
            {
                "schema": SCHEMA,
                "provider": "umai",
                "source": "umai-email-fixture",
                "provider_event_id": "late-window",
                "kind": "created",
                "reservation_id": "NL-2220",
                "source_message_time": "2026-11-14T16:50:00+00:00",
                "service_date": "2026-11-14",
                "time": "22:00",
                "party": 2,
                "live": False,
                "synthetic": True,
                "freshness": "starts after the candidate",
            },
        )
        created = intake(self.store, _message("instagram-party-of-four.json"), self.config, self.snapshot)
        checked = check(self.store, created["request"]["id"], self.snapshot, self.config)
        self.assertEqual(checked["offered"], [{"date": "2026-11-14", "time": "21:30", "party": 4}])
        self.assertNotIn("NL-2220", checked["availability"]["uncertain_reservation_ids"])
        rows, blocked = reconcile(self.store, self.snapshot, "2026-11-14", self.config)
        self.assertEqual(blocked, "")
        self.assertIsNone(rows["umai:NL-2220"]["end"])

    def test_older_notice_cannot_overwrite_a_newer_one(self) -> None:
        from integrations.events import SCHEMA, record_event
        from integrations.workflow import reconcile

        def notice(event_id: str, stamp: str, clock: str) -> None:
            record_event(
                self.store,
                {
                    "schema": SCHEMA,
                    "provider": "umai",
                    "source": "umai-email-fixture",
                    "provider_event_id": event_id,
                    "kind": "updated",
                    "reservation_id": "NL-1042",
                    "source_message_time": stamp,
                    "service_date": "2026-11-14",
                    "time": clock,
                    "party": 2,
                    "live": False,
                    "synthetic": True,
                    "freshness": "ordering test",
                },
            )

        notice("newer", "2026-11-14T18:00:00+00:00", "20:00")
        notice("older", "2026-11-14T17:00:00+00:00", "18:00")
        rows, blocked = reconcile(self.store, self.snapshot, "2026-11-14", self.config)
        self.assertEqual(blocked, "")
        self.assertEqual(rows["umai:NL-1042"]["start"], "20:00")
        notice("tied", "2026-11-14T18:00:00+00:00", "19:30")
        _rows, blocked = reconcile(self.store, self.snapshot, "2026-11-14", self.config)
        self.assertIn("share a source time", blocked)

    def test_dedup_is_namespaced_and_a_rejected_event_can_be_replayed(self) -> None:
        from integrations.events import SCHEMA, event_key, record_event

        base = {
            "schema": SCHEMA,
            "source": "umai-email-fixture",
            "provider_event_id": "shared-evt",
            "kind": "created",
            "source_message_time": "2026-11-14T16:10:00+00:00",
            "service_date": "2026-11-14",
            "time": "18:00",
            "party": 2,
            "live": False,
            "synthetic": True,
            "freshness": "dedup test",
        }
        umai = dict(base, provider="umai", reservation_id="NL-3001")
        fork = dict(base, provider="thefork", source="thefork-fixture", reservation_id="TF-3001")
        self.assertNotEqual(event_key(umai), event_key(fork))
        self.assertTrue(record_event(self.store, umai)["accepted"])
        self.assertTrue(record_event(self.store, fork)["accepted"])
        self.assertEqual(len(self.store.data["notices"]), 2)
        broken = dict(base, provider="umai", reservation_id="NL-3002", provider_event_id="fix-me", party=None)
        rejected = record_event(self.store, broken)
        self.assertFalse(rejected["accepted"])
        self.assertNotIn(rejected["dedup_key"], self.store.data["seen_message_ids"])
        fixed = dict(broken, party=2, service_date="2026-02-31")
        still_bad = record_event(self.store, fixed)
        self.assertIn("service date", still_bad["reason"])
        repaired = dict(broken, party=4)
        accepted = record_event(self.store, repaired)
        self.assertTrue(accepted["accepted"])
        self.assertFalse(accepted["duplicate"])

    def test_verified_duration_is_a_real_window_and_an_unverified_number_is_not(self) -> None:
        from integrations.events import SCHEMA, record_event

        ingest_file(self.store, ROOT / "fixtures" / "emails" / "03-cancelled-nl-0770.eml", self.config)
        record_event(
            self.store,
            {
                "schema": SCHEMA,
                "provider": "umai",
                "source": "umai-email-fixture",
                "provider_event_id": "duration",
                "kind": "created",
                "reservation_id": "NL-3333",
                "source_message_time": "2026-11-14T16:50:00+00:00",
                "service_date": "2026-11-14",
                "time": "20:00",
                "party": 2,
                "live": False,
                "synthetic": True,
                "freshness": "duration test",
            },
        )
        created = intake(self.store, _message("instagram-party-of-four.json"), self.config, self.snapshot)
        request_id = created["request"]["id"]
        claimed = json.loads(json.dumps(self.config))
        claimed["rules"]["turn_time_minutes"] = 120
        unclear = check(self.store, request_id, self.snapshot, claimed)
        self.assertEqual(unclear["offered"], [])
        self.assertIn("NL-3333", unclear["availability"]["uncertain_reservation_ids"])
        claimed["rules"]["turn_time_verified"] = True
        covered = check(self.store, request_id, self.snapshot, claimed)
        self.assertEqual(covered["availability"]["duration_rule"], "verified")
        self.assertEqual(covered["offered"], [])
        self.assertNotIn("NL-3333", covered["availability"]["uncertain_reservation_ids"])
        self.assertIn("NL-3333", [row["reservation_id"] for row in covered["availability"]["conflicts"]])

    def test_a_feed_that_cannot_be_ordered_stops_the_exports(self) -> None:
        from integrations.calendar import build_ics
        from integrations.events import SCHEMA, record_event
        from integrations.workflow import calendar_plan, confirmed_rows

        base = {
            "schema": SCHEMA,
            "provider": "umai",
            "source": "umai-email-fixture",
            "kind": "created",
            "reservation_id": "NL-5001",
            "source_message_time": "2026-11-14T17:00:00+00:00",
            "service_date": "2026-11-14",
            "time": "19:00",
            "party": 2,
            "live": False,
            "synthetic": True,
            "freshness": "tie test",
        }
        record_event(self.store, dict(base, provider_event_id="first"))
        record_event(self.store, dict(base, provider_event_id="second", time="20:00"))
        for build in (
            lambda: build_pdf(self.store, self.snapshot, self.config, "2026-11-14"),
            lambda: build_ics(self.store, self.snapshot, self.config, "2026-11-14"),
            lambda: confirmed_rows(self.store, self.snapshot, "2026-11-14", self.config),
            lambda: calendar_plan(self.store, self.snapshot, "2026-11-14", self.config),
        ):
            with self.assertRaises(WorkflowError) as refused:
                build()
            self.assertIn("cannot be ordered", refused.exception.code)
            self.assertIn("NL-5001", refused.exception.code)

    def test_a_bad_fixture_file_is_held_and_the_batch_continues(self) -> None:
        from integrations.thefork import ingest_dir as ingest_thefork

        folder = Path(self.temporary.name) / "thefork"
        folder.mkdir()
        good = {
            "provider": "thefork",
            "provider_event_id": "evt-good",
            "kind": "created",
            "reservation_id": "TF-7001",
            "source_message_time": "2026-11-14T17:00:00+00:00",
            "service_date": "2026-11-14",
            "time": "18:00",
            "party": 2,
            "live": False,
            "synthetic": True,
        }
        (folder / "01-broken.json").write_text("{not json")
        (folder / "02-list.json").write_text("[]")
        (folder / "03-good.json").write_text(json.dumps(good))
        results = ingest_thefork(self.store, folder)
        self.assertEqual([item["accepted"] for item in results], [False, False, True])
        self.assertEqual([notice["reservation_id"] for notice in self.store.data["notices"]], ["TF-7001"])
        held = {item["source"]: item for item in self.store.data["review"]}
        self.assertIn("not readable JSON", held["01-broken.json"]["reason"])
        self.assertIn("not a JSON object", held["02-list.json"]["reason"])
        self.assertTrue(all(item["replayable"] for item in held.values()))
        self.assertNotIn("file:thefork:01-broken.json", self.store.data["seen_message_ids"])
        ingest_thefork(self.store, folder)
        self.assertEqual(len(self.store.data["review"]), 2)
        (folder / "01-broken.json").write_text(json.dumps(dict(good, provider_event_id="evt-repaired", reservation_id="TF-7002")))
        repaired = ingest_thefork(self.store, folder)
        self.assertTrue(repaired[0]["accepted"])
        self.assertFalse(repaired[0]["duplicate"])

    def test_mail_rejects_are_listed_once_and_stay_replayable(self) -> None:
        ingest_dir(self.store, ROOT / "fixtures" / "emails", self.config)
        ingest_dir(self.store, ROOT / "fixtures" / "emails", self.config)
        sources = [item["source"] for item in self.store.data["review"]]
        self.assertEqual(sorted(sources), ["05-bad-sender.eml", "06-missing-reservation.eml"])
        self.assertTrue(all(item["replayable"] for item in self.store.data["review"]))

    def test_approval_refusal_names_the_withheld_slot(self) -> None:
        from integrations.thefork import ingest_dir as ingest_thefork

        ingest_dir(self.store, ROOT / "fixtures" / "emails", self.config)
        ingest_thefork(self.store, ROOT / "fixtures" / "thefork")
        created = intake(self.store, _message("instagram-party-of-four.json"), self.config, self.snapshot)
        request_id = created["request"]["id"]
        check(self.store, request_id, self.snapshot, self.config)
        with self.assertRaises(WorkflowError) as refused:
            approve(self.store, request_id, "2026-11-14", "21:30", 4, self.config, self.snapshot)
        self.assertIn("21:30 is withheld", refused.exception.code)
        self.assertIn("NL-1042", refused.exception.code)
        self.assertIn("TF-2201", refused.exception.code)
        with self.assertRaises(WorkflowError) as conflict:
            approve(self.store, request_id, "2026-11-14", "20:00", 4, self.config, self.snapshot)
        self.assertIn("NL-0881", conflict.exception.code)

    def test_a_party_above_the_slot_maximum_is_not_offered(self) -> None:
        ingest_file(self.store, ROOT / "fixtures" / "emails" / "03-cancelled-nl-0770.eml", self.config)
        message = dict(_message("instagram-party-of-four.json"))
        message.update(
            {
                "thread_id": "ig-thread-4500",
                "message_id": "ig-msg-4500",
                "text": "Could we book a table for seven tonight at 21:30?",
            }
        )
        created = intake(self.store, message, self.config, self.snapshot)
        request_id = created["request"]["id"]
        checked = check(self.store, request_id, self.snapshot, self.config)
        self.assertEqual(checked["party"], 7)
        self.assertEqual(checked["offered"], [])
        self.assertEqual(checked["status"], "needs_staff_review")
        self.assertEqual(checked["availability"]["conflicts"], [])
        self.assertEqual(checked["availability"]["slots_above_party_max"], [{"time": "21:30", "party_max": 6}])
        self.assertIn("above the slot maximum of 6", checked["availability"]["requested_slot"])
        with self.assertRaises(WorkflowError) as refused:
            approve(self.store, request_id, "2026-11-14", "21:30", 7, self.config, self.snapshot)
        self.assertIn("party of 7 is above the maximum of 6 for 21:30", refused.exception.code)
        self.assertEqual(self.store.request_by_id(request_id)["status"], "needs_staff_review")

    def test_a_time_the_house_does_not_list_is_not_offered(self) -> None:
        ingest_file(self.store, ROOT / "fixtures" / "emails" / "03-cancelled-nl-0770.eml", self.config)
        message = dict(_message("instagram-party-of-four.json"))
        message.update(
            {
                "thread_id": "ig-thread-4600",
                "message_id": "ig-msg-4600",
                "text": "Table for two tonight at 22:30 please",
            }
        )
        created = intake(self.store, message, self.config, self.snapshot)
        request_id = created["request"]["id"]
        checked = check(self.store, request_id, self.snapshot, self.config)
        self.assertEqual(checked["time"], "22:30")
        self.assertEqual(checked["availability"]["conflicts"], [])
        self.assertEqual(checked["availability"]["requested_slot"], "not a slot the house offers")
        self.assertEqual(checked["offered"], [{"date": "2026-11-14", "time": "21:30", "party": 2}])
        with self.assertRaises(WorkflowError) as refused:
            approve(self.store, request_id, "2026-11-14", "22:30", 2, self.config, self.snapshot)
        self.assertIn("not one of the offered", refused.exception.code)

    def test_approval_checks_the_notice_feed_again(self) -> None:
        ingest_file(self.store, ROOT / "fixtures" / "emails" / "03-cancelled-nl-0770.eml", self.config)
        created = intake(self.store, _message("instagram-party-of-four.json"), self.config, self.snapshot)
        request_id = created["request"]["id"]
        check(self.store, request_id, self.snapshot, self.config)
        follow = intake(self.store, _message("instagram-follow-up.json"), self.config, self.snapshot)
        self.assertEqual(follow["request"]["status"], "awaiting_staff_booking_approval")
        self.assertEqual(follow["request"]["offered"], [{"date": "2026-11-14", "time": "21:30", "party": 4}])
        ingest_file(self.store, ROOT / "fixtures" / "emails" / "01-new-nl-1042.eml", self.config)
        with self.assertRaises(WorkflowError) as refused:
            approve(self.store, request_id, "2026-11-14", "21:30", 4, self.config, self.snapshot)
        self.assertIn("21:30 is withheld", refused.exception.code)
        self.assertIn("NL-1042", refused.exception.code)
        after = self.store.request_by_id(request_id)
        self.assertEqual(after["status"], "needs_staff_review")
        self.assertEqual(after["offered"], [])
        self.assertIsNone(after["approval"])
        self.assertEqual(after["history"][-1]["event"], "availability_checked")

    def test_event_follow_up_date_must_be_a_real_date(self) -> None:
        event = intake(self.store, _message("email-event.json"), self.config, self.snapshot)
        request_id = event["request"]["id"]
        event_questions(self.store, request_id, ["guest count"], self.config)
        with self.assertRaises(WorkflowError) as refused:
            event_send(self.store, request_id, "2026-02-31")
        self.assertIn("real", refused.exception.code)
        self.assertIsNone(self.store.request_by_id(request_id)["outbound"])
        sent = event_send(self.store, request_id, "2026-11-18")
        self.assertEqual(sent["status"], "follow_up_due")

    def test_review_command_lists_held_files(self) -> None:
        environment = dict(os.environ)
        environment["TABLELINE_STORE"] = str(Path(self.temporary.name) / "cli.json")
        for command in (["ingest"], ["review"]):
            completed = subprocess.run(
                [sys.executable, "-m", "integrations", *command],
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)["result"]
        self.assertEqual(payload["count"], len(payload["held"]))
        sources = {item["source"] for item in payload["held"]}
        self.assertIn("05-bad-sender.eml", sources)
        fork = [item for item in payload["held"] if item["provider"] == "thefork"]
        self.assertTrue(any("missing party" in item["reason"] for item in fork))
        self.assertTrue(all(item["replayable"] for item in payload["held"]))
        self.assertIn("ingested again", payload["note"])


if __name__ == "__main__":
    unittest.main()
