# Adapters

These are the checks the coordinator runs from the Switch room. They do not open Instagram, Gmail, or UMAI.

| Module | What it does | Status |
|---|---|---|
| `mailbox.py` | Reads the UMAI-shaped `.eml` fixtures and emits a reservation event. | Matches the fixture contract in `fixtures/restaurant.json`. |
| `thefork.py` | Reads `fixtures/thefork/` and emits the same event. | Does not call api.thefork.io. |
| `events.py` | Deduplicates, and holds incomplete or unrecognized events for staff. A file that cannot be read is held too, and the batch goes on. | Shared by both adapters. A held item is not marked seen, so a corrected copy can be ingested. |
| `workflow.py` | Classifies a guest fixture, checks it against the snapshot plus accepted notices, and records a reference after the local checks. | `approve` reconciles the snapshot and the notice feed again and checks that the slot is still offered. `reference` checks the id shape and local duplicates. Neither reads a booking API or checks who ran the command. |
| `pdf.py` | Builds the daily list for one service date. | Pending requests on another date are counted and left off the page. Refuses to build when two notices for one reservation cannot be ordered. |
| `calendar.py` | Writes an `.ics` file for rows with a known start and end. | Notices and typed references are named and left out. Same refusal as the PDF. |
| `__main__.py` | Runs those steps from the Tableline directory. | `python3 -m integrations ingest` reads both fixture folders. `review` lists what was held. |

`var/store.json` is created in the directory of the process that ran the command. The template tells the coordinator to run the commands. The booking and guest agents work from the coordinator's posts. A test with two directories showed two ledgers.

Keep tokens out of this repository and out of room messages.

Instagram in this repo is a fixture file. A live connection would need a professional account, Meta's messaging permissions, a webhook, app review, and the reply window. None of that was set up.

Gmail can read and send through its API, and push needs Google Pub/Sub. Neither is connected.

Computer use is not how this project reads the book. A screen nobody is watching is a poor record of a booking.
