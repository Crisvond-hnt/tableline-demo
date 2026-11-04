# What a pilot still needs

Nothing here is a request for a password, an API key, or a guest's contact details. Redacted samples are enough. Leave real addresses and names out.

## Repository

- The git URL the coordinator's machine can clone is `https://github.com/Crisvond-hnt/tableline-demo.git`. A private fork still has to be reachable from that machine. Older copies under other accounts are backups. Do not use them for this demo.

## Booking records

Send redacted samples, not the mailbox password and not a guest's phone or email.

- One UMAI notice for a new reservation, one for an edit, and one for a cancel. Include the From header, the subject, and the body with the guest's contact details removed. The settings screen shows that those three emails exist. It does not show whether the body contains the reservation id, date, time, and party. Until those three samples exist, the parser stays on the fixture contract in `fixtures/emails/`.
- If the account can export one service day, a redacted copy of that file, the format, and whether someone downloads it by hand. The demo snapshot is not that export.
- For TheFork, a yes or no on partner API access. If yes, one redacted webhook or `GET /v1/reservations/{id}` body. The files in `fixtures/thefork/` are not that body. Do not send a client id or client secret.
- For OpenTable, a yes or no from the account manager on which APIs the restaurant may call. There is no OpenTable fixture until that answer exists. Do not send API keys.

## House rules

- Opening hours and any closed dates.
- Table areas and how many people each area can seat.
- How long a booking lasts, and any buffer between bookings. Until this is known, the calendar file cannot invent a duration for a notice that only has a clock time.
- Party-size limits.
- Who may approve a slot, and who may approve the words sent to a guest. The current room contains only the person who creates it. Extra staff need to be invited, and all three agents still answer only that owner unless their addressing is changed.

## Channels

- Which channels actually receive reservation requests today.
- Which of those already land in the booking system.
- Which staff need to be in the Switch room.

## Daily output

- Whether the shift needs the PDF, the `.ics` file, or both.
- Which columns the PDF must show.
- Whether a row without a known duration should stay on the PDF only, which is what this build does.
