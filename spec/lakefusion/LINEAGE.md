# Versioned golden-record provenance v1

LM-006 publishes a bounded, complete domain snapshot through the existing
immutable multi-output publisher. A publication contains golden records,
attribute lineage, source versions, source memberships and contract definitions.
Local fixtures use JSON files with the SQLite commit catalog; the Databricks
adapter uses version-zero Delta tables and the existing serialized-job catalog.
The same portable transformation constructs both projections.

Each golden record has a **master revision**, separate from its operational
identity revision. Source changes, new policy/configuration or a new evaluation
snapshot advance the master revision even when company membership is unchanged.
Exact calculations retain their revision across publications. Readers select a
committed publication ID and then use only its manifest; historical reads never
resolve current source tables, policies or model aliases.

Stored evidence includes the complete scalar calculation and its input records,
approved domain/policy receipts, the exact mapping definitions, all candidate
values and exclusions, override decisions, source versions and value hashes.
Field rows expose the selection reason and winning source or override reference.
An explicit matching context pins ruleset/configuration IDs, versions and hashes;
a model reference is either an immutable URI/version/hash or null. The integration
fixture uses declared truth memberships and **no matching model**. This is not a
new automatic-merge quality claim.

New publications replay calculations against the recorded mapping/policy inputs
and the current implementation, rejecting inconsistent or review-required results.
Reads validate stored checksums and projections without invoking the current
survivorship algorithm. An algorithm upgrade therefore does not silently rewrite
historic explanations. Checksums detect damage, not malicious changes by a
privileged administrator who can rewrite all data and hashes.

The caller explicitly names the expected previous publication. Within the
serialized publisher, stale heads, source-version rollback, reuse of a source
version with changed content, identity-revision rollback and unannounced removal
of a master are refused. A retry of a previously committed batch returns its
original publication without moving the current head backward. Source tombstones
remain in source history/crosswalks; valid remaining values can be published.
Retiring masters and merge/split publication reconciliation remain LM-009/011.

Limits per publication: 100 masters, 2,000 source records, 10,000 field rows and
32 MiB serialized snapshot. This first reader is an internal bounded export/detail
service, not the scalable or authorized entity API. The local adapter retains all
committed attempts. Delta tables require the existing single-concurrency job
discipline and must not be mutated or vacuumed away while referenced.

Approval receipts and identity snapshots come from trusted workers. This package
checks consistency, not user authentication or latest operational watermarks.
LM-007/008/009 still own authenticated approval, outbox delivery, current-state
rechecks, command acknowledgment and recovery across Postgres/Delta. No
cross-system exactly-once or production retention/backup claim is made here.
