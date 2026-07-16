# Global repair and escalation budget

Every plan instance has one monotonic ledger shared by all repair and escalation
tiers. A reservation charges worst-case tokens and wall milliseconds before an
attempt starts, plus the appropriate attempt-kind count. Model, expert, and
reservation changes cannot reset an attempt identity. Reservations are atomic,
replay-safe, and never refunded, preventing concurrency oversubscription and
reserve-run-refund gaming.

Exceeding token, time, repair, or escalation ceilings returns no reservation;
the attempt must not start. Three strict schemas expose policy, reservation, and
snapshot evidence. Canonical evidence admits one repair and one escalation, then
rejects both an over-budget repair and an attempt-ID replay.
