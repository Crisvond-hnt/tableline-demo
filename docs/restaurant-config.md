# Restaurant configuration

`fixtures/restaurant.json` is the fictional restaurant Northline. `synthetic` is true. The UMAI mailbox block and the TheFork files are fixture contracts. `python3 -m integrations configure` does not turn either of them into a live account.

`python3 -m integrations configure` reads the file and prints which of those rules are still `unknown`. `TABLELINE_CONFIG` selects another file. A daily output, when stated, is `pdf`, `ics`, or `both`. A source status, when stated, is `not_connected`, `manual`, or `fixture`. An email address is rejected.

Leave a rule as `unknown` until a staff member supplies it. `turn_time_minutes` is used for a notice end time only when `turn_time_verified` is also true. The sample sets neither. A notice without that rule does not clear later slots. Snapshot bookings keep the start and end written in `fixtures/snapshot.json`.

The mailbox block is the synthetic sender contract:

- `allowed_from_domains`: `notify.example.test`
- `subject_pattern`: `Reservation (new|edited|cancelled): NL-<digits>`
- The body must repeat the restaurant, the reservation id, the status word, the date, the time, and the party.

Replace that contract only after a redacted real notice has been compared with it. Do not paste a real recipient address into this file.

`acknowledgment_enabled` is false. The room does not send "we're checking" on its own.

Timezone is `Europe/Lisbon`. "Tonight" is the date of `received_at` in that zone.
