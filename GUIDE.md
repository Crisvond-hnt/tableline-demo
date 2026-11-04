# How this room answers

Read `fixtures/restaurant.json` and `fixtures/snapshot.json` before you talk about a time.

- The snapshot is not live. Quote its `generated_at`.
- A conflict is a reservation id and a window. Do not name the other guest.
- Notice files are intake. A notice with no verified duration does not make a later slot free. Say that the slot is withheld.
- UMAI-shaped mail and TheFork-shaped JSON in this repo are fixtures. Do not describe either as a live API read. `source_message_time` is the time on the file, not a mailbox delivery.
- APPROVE reads the snapshot and the notice feed again, then checks that the slot is still offered. It does not check who ran the command; the room's addressing keeps that to the owner.
- REFERENCE checks the id shape and this folder's store and snapshot. It does not read UMAI.
- The confirmation text says the reference was recorded locally. The send is simulated.
- An event inquiry is not a table. Staff name the questions. The follow-up date is one the owner supplies.
- Opening hours, turn time, and party limits are unknown until staff write them into the configuration. Do not invent them.
- Only the coordinator runs commands. The ledger is `var/store.json` in that agent's folder.
