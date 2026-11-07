# Tableline

A guest writes on Instagram. The booking platform emails a notice. A partner site sends its own reservation. A wedding inquiry lands the same afternoon. Someone on the floor still has to work out what is free, and what to answer. The booking system the restaurant already uses stays the book.

Tableline is one Switch room for that decision. Each source it has been given becomes the same kind of reservation event. The room shows the conflict or the missing fact. Nothing is written, and no guest is answered, until a person on the team says so.

```text
request or notice → source adapter → shared event → Switch room → staff decision → daily PDF / calendar file
```

Northline, the restaurant in this repository, is fictional. Every guest is invented. Nothing calls a booking API, polls a mailbox, or sends a message.

## What the channel shows

The private channel is `northline-reservations`. The owner asks whether Mara Quinn can have four people at 8:00 on 14 November 2026.

- 8:00 is taken. NL-0881 is seated from 7:30 to 9:00. The other guest is not named.
- 9:30 is not offered. NL-1042 and TF-2201 start that evening and have no verified finish time, so a later slot waits for a person.
- Four notices are held for a person: one from the wrong sender, one missing the reservation, one with no party size, and one that is not a new booking, a change, or a cancellation.
- The book is unchanged. Mara is not contacted.

The booking agent says to leave 8:00 alone. The guest agent says not to message her yet.

## How Switch is used

Switch connects an agent that is already signed in, Claude Code, Codex, or OpenCode, to the chat app that server already uses: Slack, Discord, Microsoft Teams, or Mattermost. Telegram cannot create the channel, so it is not the bridge. Cursor edited this repository. It is not an agent in the room.

`templates/tableline.template.yaml` opens one private channel, `{team}-reservations`, with the person who created it and three agents. In the demo, `team` is `northline`.

| Agent | What it does | Who can instruct it |
|---|---|---|
| `{team}-coordinator` | Runs every Tableline command and posts the spoken result. Its ledger is `var/store.json` in its own folder. | The owner, and that owner's agents. |
| `{team}-booking` | Says whether the time in that post is really open. Does not run a command and does not write a reservation. Holds the exclusive `booking-writer` job. | The same owner. |
| `{team}-guest` | Says whether anyone should reply yet. Does not send the reply. Holds the exclusive `guest-sender` job. | The same owner. |

Switch enforces this with each agent's addressing set to `owner-agents`. A person invited later can read the channel. They cannot approve. Auto mode and bypass permissions are off on all three, so the runtime asks before it acts.

Two room documents, `integration` and `approval`, are what an agent reads before it claims a system was updated. A reference typed in the room is a note in the coordinator's folder. It is not a read from the booking platform. The guest reply that follows is stored as `simulated` and is not delivered.

## Run it

Python 3.9 or newer. Nothing to install.

```bash
git clone https://github.com/Crisvond-hnt/tableline-demo.git
cd tableline-demo
python3 -m integrations configure
python3 -m unittest discover -s tests -t . -v
python3 -m integrations demo
```

`configure` lists the house rules that are still `unknown`. `demo` runs the fixture night in a temporary ledger and does not write `var/store.json`. It prints the conflict with NL-0881, an empty offered list, 21:30 withheld because of NL-1042 and TF-2201, the refusal that names those two reservations, and the calendar rows that have a real start and end. `python3 -m integrations review` lists what was held for a person instead of accepted.

The same checks in a channel:

1. Open Switch Console, start a local server, and sign in Claude Code, Codex, or OpenCode under **Settings**, then **Agent providers**.
2. Import `templates/tableline.template.yaml` and use it.
3. Set **team** to `northline`, **Repository** to `https://github.com/Crisvond-hnt/tableline-demo.git`, **Provider** to the signed-in agent, and **Bridge** to the app already connected. On a local server that is Mattermost.
4. Create the room. Switch makes `northline-coordinator`, `northline-booking`, `northline-guest`, and the private channel `northline-reservations`. You are the only person in it.

```text
@northline-coordinator Mara wants four people tonight at 8. Can we take it?
@northline-booking What would you do?
@northline-guest Can we reply to her?
```

The clicks from a fresh install, including Slack, are in `docs/SERVER_SETUP.md`.

## The fixture night

The snapshot is `fixtures/snapshot.json`, marked `live: false`, generated at 16:00 UTC on 14 November 2026. NL-0881 runs 19:30 to 21:00. NL-0902 runs 18:00 to 19:15. NL-0770 runs 21:30 to 22:30 until a newer notice cancels it.

A slot is offered only when the house lists it, the party fits that slot's maximum, and nothing on the reconciled feed covers it. Approval reads the snapshot and the notices again at that moment, and it has to match an offered date, time, and party size exactly. A notice that arrives after the offer can still refuse it. The tests approve 21:30 only on the narrower feed whose only change is the cancellation of NL-0770, which already had a start and an end. On the full night, that same approval is refused.

Lee Okonkwo's note is a wedding, so it stays an event. The owner names the questions and the follow-up date. The reply is simulated.

The PDF is the list for that service. The `.ics` file includes only rows with a known start and end, so NL-0881 and NL-0902 are in it. Notices without a duration are named and left out. If two notices for one reservation cannot be put in order, both files are refused. Neither file is a live sync, and the calendar file is not connected to Google Calendar.

UMAI-shaped email is parsed by `integrations/mailbox.py`. TheFork-shaped JSON is parsed by `integrations/thefork.py`. Both emit `tableline.reservation_event.v1`. A third source is another adapter that writes that same object. Deduplication, timestamps, and turn time are specified in `docs/schema.md` and `docs/lifecycle.md`.

## What is connected

| Input | In this repository |
|---|---|
| Dated snapshot | Synthetic file, `fixtures/snapshot.json`, `live: false`. The conflict check uses it. |
| UMAI-shaped email | Parser for the fixture contract in `fixtures/emails/`. No mailbox is polled. |
| TheFork-shaped JSON | Parser for `fixtures/thefork/`. [TheFork's partner API](https://docs.thefork.io/B2B-API/introduction) is not called. |
| OpenTable | Not connected. Their APIs need partner approval: [docs.opentable.com](https://docs.opentable.com/). No fixture and no client. |
| Guest messages | Fixture files. Replies are simulated and not delivered. |
| UMAI API | No public API found on [umai.io](https://www.umai.io/). No client in this code. |
| Daily PDF and `.ics` | Written from the snapshot and the local ledger. Unknown durations are left out of the calendar file. |

The longer table, with the provider documentation that was checked, is `docs/integration-matrix.md`.

## Another restaurant

Copy `fixtures/restaurant.json`, or point `TABLELINE_CONFIG` at another file. `python3 -m integrations configure` accepts `unknown`. It rejects a blank rule, a source marked `connected`, and an email address outside `example.test`, `example.com`, and `example.invalid`.

The sample leaves hours, service windows, party size, turn time, buffers, closed dates, areas, capacities, approval roles, sources, and daily output unknown on purpose. The field notes are in `docs/restaurant-config.md`. What a restaurant hands over to go live, including redacted notices, is `docs/pilot-inputs.md`.

## Where to read next

- `docs/SERVER_SETUP.md` covers Switch Console from a fresh install.
- `demo/SCRIPT.md` is the order the recording follows.
- `GUIDE.md` is how the three agents speak in the room.
- `docs/schema.md` and `docs/lifecycle.md` are the event and request shapes.
- `integrations/README.md` is what each module does.

The code is under the MIT license.
