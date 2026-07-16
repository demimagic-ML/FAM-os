# User preference adapters

Phase 11.3 stores only four normalized policy priorities: quality, energy, latency, and explanation detail. Profiles are owner-bound, atomically written, mode `0600`, inspectable, and resettable with a receipt naming every removed key.

Preferences cannot represent permission, verification, trust, or safety exceptions and therefore cannot weaken those boundaries.
