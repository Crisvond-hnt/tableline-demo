# Integration matrix

Checked on 4 November 2026.

UMAI's public site, [umai.io](https://www.umai.io/), describes real-time inventory, table management, and guest messaging. It does not publish an API. The restaurant's own settings can email new, canceled, and edited reservations. That screen does not show the sender, subject, or body, so the parser in this repo matches the fixtures only.

TheFork's partner docs are [the B2B introduction](https://docs.thefork.io/B2B-API/introduction) and [authentication](https://docs.thefork.io/B2B-API/authentication). They describe availabilities, reservation create/update, webhooks, and a client id plus secret sent through a safe channel. That is a partnership. It is not something every restaurant already has turned on. This repo does not call `api.thefork.io`.

OpenTable's docs are [docs.opentable.com](https://docs.opentable.com/) and the [API partner FAQ](https://www.opentable.com/restaurant-solutions/api-partners/faqs/). Production access needs approval and an agreement. A restaurant is told to talk to its account manager. Not every API is available to every account. This repo has no OpenTable client and no OpenTable fixture.

Switch's template fields used here are in the [template language](https://github.com/sandbox-quantum/switch/blob/main/docs/TEMPLATES.md) on the Switch repository `main` branch, and the import button is documented at [Templates](https://docs.switchagents.ai/switch-rooms/administer/room-templates). Auto mode is documented at [agent settings](https://docs.switchagents.ai/switch-rooms/getting-started/agent-settings). On OpenCode, auto mode approves every action, so this template sets `auto_mode: false`.

| Path | Inbound | Availability read | Booking write | Outbound reply | Freshness |
|---|---|---|---|---|---|
| UMAI API or webhook | No public document found. | No public document found. | No public document found. | No public document found. | — |
| UMAI status email | Parser for the synthetic contract in `fixtures/emails/`. Real sender, subject, and body are still unknown. | A notice is not an availability search. Without a verified duration it withholds later slots. | None. | None. | `source_message_time` is the Date header. `ingested_at` is local record time. No mailbox is polled. |
| UMAI export | — | `fixtures/snapshot.json`, labeled `live: false`, provider `umai`. A real export format was not verified. | None. | None. | `generated_at` on the file. |
| TheFork B2B API | Not called. Partnership credentials would be required. | Not called. Their docs describe availability for partners. | Not called. | Not called. | — |
| TheFork fixture | `fixtures/thefork/` through the same event recorder as the email fixtures. | Clock time only. Later slots are withheld when duration is unknown. | None. | None. | `source_message_time` on the fixture. |
| OpenTable API | Not connected. Approval and an agreement come first. | Not connected. | Not connected. | Not connected. | — |
| Instagram | Fixture only. | — | — | Simulated id after approval. Nothing is delivered. | The fixture's `received_at`. |
| Guest email | Fixture only. No mailbox is polled. | — | — | Simulated id for the event draft. Nothing is delivered. | The fixture's `received_at`. |
| Website form | Not connected. | — | — | — | — |
| Daily PDF | — | Snapshot, notices, and locally recorded references for that service date. Other dates are counted and left off. | None. | A local PDF. | Generated time is printed on the page. |
| `.ics` | — | Rows with a known start and end. Notices and typed references are named in COMMENT lines and left out. | None. | A local file. Not a Google Calendar connection. | Snapshot `generated_at`, Europe/Lisbon converted to UTC. |

Permission and approval:

- `addressing: owner-agents` on all three agents means the deployer and that person's other agents, per the template language. A later invite can read the channel and cannot instruct any of them, so the APPROVE and REFERENCE the coordinator runs are the owner's.
- The room starts with `{$creator}` only. An empty user field is not allowed, and this template does not invent a staff username.
- `auto_approve` is false. `auto_mode` is false.
- APPROVE reads the snapshot and every accepted notice again and checks that the slot is still offered; a slot is offered only when the house lists it, the party fits its maximum, and nothing on the feed covers it. REFERENCE checks the id against the coordinator's local store and snapshot. Neither command checks who ran it, and neither calls a booking API. Switch does not parse those words. The `repo` field tells a managed agent to clone the git URL. Without agent management, Console does a shallow clone, and the agent clones it if that fails. The template contains no laptop path.
- A file that cannot be read, and an event that fails validation, are held for review and listed by `python3 -m integrations review`. Held items are not marked seen. The daily PDF and the `.ics` file are refused when two notices for one reservation share a source time and cannot be ordered.
