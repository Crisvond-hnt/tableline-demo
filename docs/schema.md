# Request schema

A request is one inbound conversation. The integration store keeps its id, thread, approval, and history. The booking system keeps the reservation.

| Field | Meaning |
|---|---|
| `id` | Stable id derived from the channel and thread. |
| `received_at` | Timestamp on the inbound message. |
| `channel` | `instagram` or `email` in the fixtures. Neither is a live connection. |
| `thread_id` | Provider thread. A later message with the same thread updates the request. |
| `message_ids` | Every provider message id already applied. A repeat is ignored. |
| `dedup_key` | Channel plus the first message id. |
| `classification` | `direct_reservation`, `event_inquiry`, `reservation_change`, or `non_reservation`. |
| `status` | See `docs/lifecycle.md`. |
| `guest_name` | Present only when the fixture or the guest stated it. |
| `service_date`, `time`, `party` | Extracted from the text. Missing pieces stay missing. |
| `missing` | The facts still required before an availability check. |
| `history` | Append-only. Each entry has a timestamp, an actor, and a short detail. |
| `availability` | The snapshot time, the source label, and conflict ids. `live` is false. |
| `offered` | The slots APPROVE can accept: listed by the house, within that slot's party maximum, and clear on the reconciled feed. APPROVE rebuilds this list before it accepts one. |
| `approval` | The owner's date, time, party, and the action `write-and-confirm`. |
| `booking_reference` | An id a person typed. Accepted after a local pattern and duplicate check. Not read from a booking API. |
| `outbound` | Present only after a simulated send, with `result: simulated` and a provider message id. |
| `follow_up_due` | A date the owner typed for an event. The software does not invent one. |
| `questions` | The exact questions staff asked the event draft to include. |

Allergy and accessibility notes are not interpreted. If a guest states one, staff handle it. The fixtures do not include any.

## Reservation event

Every source adapter writes the same object before the ledger will keep it. The schema name is `tableline.reservation_event.v1`.

| Field | Meaning |
|---|---|
| `provider` | `umai` or `thefork` in this demo. |
| `source` | `umai-email-fixture` or `thefork-fixture`. |
| `provider_event_id` | Part of the dedup key, with provider, source, and kind. A repeat of an accepted key is ignored. A rejected event is not marked seen, so a corrected copy can be recorded. |
| `kind` | `created`, `updated`, or `cancelled`. Anything else is unrecognized and goes to review. |
| `reservation_id` | The id inside that provider. It does not merge with another provider's id. |
| `source_message_time` | The email Date header or the time written on the fixture. Not a mailbox delivery time. |
| `ingested_at` | When this process recorded the file. |
| `service_date`, `time`, `party` | Required for an accepted notice. A missing or impossible value goes to review. |
| `live` | Always false here. |
| `synthetic` | Always true here. |
| `freshness` | A sentence stored with the notice saying what the timestamp is and which API was not called. |

An accepted event becomes a notice. Conflict checks start from `fixtures/snapshot.json`. A newer notice can update or cancel the matching provider row. An older notice does not replace a newer row. A notice without a verified duration does not clear later slots.
