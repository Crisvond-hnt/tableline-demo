# Pilot interview

Ask these with a staff member. Write the answer beside the question, and mark it observed or assumed. Do not log into UMAI, Instagram, or email, and do not message a guest, unless that exact access was authorized for that visit.

Do not copy a real guest name, phone number, or email into this repository.

## What is already known

- Observed on the public site `https://www.umai.io/`: UMAI describes reservation inventory, table management, and guest messaging. No API is published there.
- Reported, not re-checked from this repository: the pilot account has an email setting for new, cancelled, and edited reservations. The message body, the stable id, the sender, and which booking sources trigger it are still unknown.
- Assumed, and not a finding: requests that start on Instagram or in a mailbox are the ones that miss the booking system. Staff have to confirm or reject that.

## Questions

1. Which channels actually receive reservation requests, and which of those already land in UMAI?
2. Does this account have a documented API or partner access that can read availability, create a booking, read the booking id back, and report later changes? If the public site cannot answer, ask UMAI support.
3. If a write API is not available, who enters the approved slot in UMAI, and which id should Tableline require before a guest is told it is booked?
4. After a controlled new, edit, and cancel, which mailbox receives the notice? From a redacted sample: sender, subject, body fields, reservation id, provider message id, how long it took, and whether staff-entered, website, and partner bookings all send one.
5. Can the account export reservations, in which file format, and can that export be scheduled? Do not infer a schedule from the existence of an export button.
6. Is computer use available in the agent Switch will run, or only in a desktop app a person is watching?
7. Is the Instagram account a professional account, and can the owner complete Meta's current permissions, webhook, app review, and reply window?
8. Which email provider is it, who can grant a least-privilege read and send scope, and which messages may be processed?
9. Where did a recent request fall through? Ask for a redacted example.
10. Which system is authoritative for availability, confirmation, cancellation, and guest contact history?
11. How is a wedding or private-dining inquiry assigned, priced, answered, and followed up today?
12. What do staff do with a conflict, a duplicate message, a missing party size, or a late reply?
13. Who may approve a booking, and who may approve the words that go to the guest?
14. Which columns does the daily list need, and which systems count as "all reservations"?
15. For a later visit, not this build: what would a live table board need to show, and who may change it?

## Retention

The pilot store should keep request ids, thread ids, and approvals for the service week, then be deleted. It is not a marketing list and it is not training data.
