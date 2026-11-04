# Lifecycle

Direct reservation:

`received` → `classified` → `needs_information` when a fact is missing → `availability_checked` (recorded in history) → `awaiting_staff_booking_approval` → `booking_write_pending` → `reference_recorded_locally` → `guest_confirmation_sent`

Event inquiry:

`received` → `awaiting_staff_questions` → `event_reply_approval` → `follow_up_due`

Also used: `needs_staff_review` when a slot cannot be cleared, including a notice with no verified duration, two notices with the same source time, a snapshot that covers the wrong date, or a conflict with nothing left to offer. `declined`, `cancelled`, and `expired` are reserved and not assigned by the demo.

A suggested time is not a hold. `guest_confirmation_sent` in this build means the simulated send was recorded after a local reference note. It does not mean a booking system confirmed the reservation, and it does not mean Instagram or email delivered the message.

No step cancels a reservation in the booking system. A cancel notice updates the daily list only after its adapter accepts it. UMAI-shaped mail and TheFork JSON both go through that recorder. A notice is not an availability search.
