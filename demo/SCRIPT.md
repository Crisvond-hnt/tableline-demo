# Demo

About three minutes. Say at the start that Northline and every guest are invented, and that the UMAI-shaped mail and TheFork-shaped JSON are fixtures. Nothing is delivered and no booking API is called.

The picture is the Switch channel. The terminal shows the checks.

1. In Switch Console, show the signed-in agent runtime under **Settings**, then **Agent providers**. Show the connected chat app on the server **Home** page. The template asks you to pick both. Import `templates/tableline.template.yaml` only when you are actually going to create the room. You would be the only person in `{team}-reservations`.
2. From a fresh clone, run `python3 -m integrations demo`. It uses a temporary ledger and prints the result. UMAI-shaped notices and TheFork-shaped notices are both in that run. Incomplete and unrecognized files stay in review, and `python3 -m integrations review` lists them. Accepted notices have `source_message_time` (the time on the file) and `ingested_at` (when the process recorded it). No mailbox was polled.
3. The result prints the snapshot time and names the conflict NL-0881, 19:30 to 21:00, for Mara's request of four at 20:00. The other guest's name is absent. `offered` is empty. `withheld_slots` shows 21:30 held back because NL-1042 and TF-2201 have a clock time and no verified duration. `approve_21_30` is a refusal that names those two ids. The snapshot is not live.
4. Say what would have to be true before a slot can be approved: the house lists that time, the party fits it, and the check, run again at the moment of approval, still offers that exact date, time, and party size. A verified turn time in the config can give a notice a real end. The sample config does not set one. The tests approve 21:30 only on a feed whose change is the cancellation of NL-0770, which already had a start and an end on the snapshot.
5. On that narrower case, confirming before a reference is refused, NL-0881 is refused because it is already on the snapshot, and NL-2044 is stored as `reference_recorded_locally`. The outbound id starts with `simulated-`. The text says the reference was not read back from a booking system. Do not play this as the outcome of `demo`.
6. An event fixture, Lee Okonkwo, stays an event. Staff name the questions. The follow-up date is one the owner types. The send is simulated.
7. The demo result lists the calendar rows. NL-0881 and NL-0902 have end times. Notices without a duration are omitted. The PDF is built in the same temporary run. NL-0770 is absent because the cancel is newer than the snapshot. The files are not a live sync and not a Google Calendar connection.

The booking and guest agents, if the room exists, can comment on what the coordinator posted. Their folders are not the ledger.
