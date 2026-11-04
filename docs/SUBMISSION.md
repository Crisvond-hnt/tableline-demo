# Submission

Requests show up in more than one place, and the booking platform is still the book. Tableline is the Switch room where one person and the coordinator sort a night of them, on a fictional restaurant called Northline.

The demo ingests two labeled fixtures through the same event format. One is a stand-in for UMAI's new, edited, and canceled emails, parsed against a contract written for the fixtures. The other is a stand-in for TheFork. TheFork documents a partner API, and this code does not call it. OpenTable's APIs are documented too, and they need approval. There is no OpenTable client here.

The owner asks the coordinator to process Mara Quinn's request, four people at 20:00 on 14 November 2026. The coordinator posts the conflict with NL-0881. It does not offer 21:30. Other notices that night have a clock time and no verified duration, so a later slot is withheld for staff review. Approving 21:30 on that feed is refused, and the refusal names the notices that held it back. A reference is recorded only after the check has offered the exact slot. If two notices for one reservation cannot be put in order, the daily list and the calendar file are refused instead of printed. The tests do that on a smaller feed: the cancel of NL-0770, which already had a start and an end. The guest reply on that path is simulated. The PDF and the `.ics` file come from the snapshot and the local ledger. Rows without a known duration are named and left out of the calendar file.

Switch is the place the decision is visible. Three agents share one private channel and do not share a folder. The coordinator runs the commands. The other two advise from the thread. The bridge is chosen from the app the server has connected. The provider is Claude Code, Codex, or OpenCode.

Another restaurant copies `fixtures/restaurant.json` and fills the rules it knows. `python3 -m integrations configure` accepts `unknown`. The sample hours, areas, capacities, and approval roles are unknown on purpose.
