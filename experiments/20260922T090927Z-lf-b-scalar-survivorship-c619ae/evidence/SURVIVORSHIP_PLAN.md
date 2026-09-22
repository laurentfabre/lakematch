# LF-B iteration 5 — scalar survivorship

Declared 2026-09-22 against `c16d790`, before execution. LF-B has consumed 4/8
slots; this bounded run consumes slot 5 even on failure.

Hypothesis: a versioned scalar policy bound to approved domain/mapping versions
can choose deterministic golden values across conflicting source records,
approved overrides, invalid values and source tombstones without stale carryover.
Use the policy in [SURVIVORSHIP.md](../../spec/lakefusion/SURVIVORSHIP.md).

Implement an additive 0004 registry migration, a portable calculator and a pilot
policy example. Test ranking criteria independently, shuffled inputs, timezone
equivalence, strict null/type semantics, approval conflicts, revocation/expiry,
full-member snapshots, source updates/deletes, all-deleted identities, drift and
address coherence. Test registry approval, immutability, retirement, upgrade and
restart with the real internal identity service and the 13-row synthetic fixture.
Allocate fixture memberships from its declared integration truth; this is not a
matching quality evaluation. Preserve branch exclusion and source namespaces.

One experiment: at most 300 seconds; pytest subprocess at most 180 seconds;
4 GiB observed main-process RSS ceiling. Enforce calculator bounds of 1,000
members, 100 fields, 200 decisions and 4 MiB JSON. PostgreSQL runs only in owned
temporary storage with TCP disabled, fsync on, 12 connections, 5-second lock and
15-second statement timeouts. Retain source/migration/plan hashes, JUnit,
sample winning-value explanations, replay hashes, duration, memory and cleanup.

No Spark, evaluation corpus, confirmation data, AI or cloud resources are used.
Portable contract and real PostgreSQL suites cover the affected compatibility
surface; old Spark identity code remains unchanged. LM-006 publication/history,
CDC, authorization and the UI stay open. Local development and commits proceed;
GitHub publication remains subject to the private-repository requirement.
