# LF-B iteration 3 — persistent identity

Declared 2026-09-22 against local commit `6fd0076`, after the durable registry.
LF-B has consumed 2/8 experiments. The first bounded run below consumes slot 3,
including a failure. Subsequent runs retain their own receipts and count.

Hypothesis: an explicitly selected PostgreSQL identity policy can preserve public
IDs when source keys change order, deduplicate concurrent reservations, retain
aliases and replay explicit merge/split outcomes across restart. Existing Spark
minimum-member IDs and frozen benchmark artifacts remain unchanged.

Implement an additive 0003 migration and optional internal worker adapter with:

- Allocated UUIDs, unique domain/source/key bindings and immutable legacy aliases.
- Caller/key/payload receipts, explicit expected revisions, actor and reason.
- Explicit merge survivor, redirects and bounded resolution. New-ID splits and
  exact restoration of a recorded merge are distinct commands. Restoration is
  refused while a participant's membership, aliases or redirect state differs
  from the recorded outcome; revisions must be current. No best-effort undo.
- Atomic source bindings, master revisions and append-only identity events.
- Approved domain-version/digest checks for new commands, with exact historical
  retries returning the original receipt even after later state changes.

Use a private temporary PostgreSQL instance, TCP disabled, fsync on, at most
12 connections, 5-second lock and 15-second statement deadlines. The first
adapter serializes identity writes; no high-throughput or distributed service
claim is intended. Bound each master/command to 1,000 source members, 1,000
aliases, 32 merge participants, 64 redirect hops, 1,000 inspected redirect
ancestors and a 1 MiB command payload.

Run relevant contract/registry/identity tests and unchanged legacy Spark identity
tests under the bounded runner: maximum 300 seconds overall, 180 seconds for the
test subprocess, 4 GiB observed main-process RSS limit. Exercise exact retries,
different payloads, stale revisions, concurrent creation/attachment/merge,
atomic rollback, database immutability, domain isolation, old alias resolution,
earlier-sorting member additions, both split policies and actual server restart.
Retain migration/source hashes, JUnit results, a compact lifecycle receipt,
time, memory and owned-process cleanup.

Use only a small synthetic integration fixture. No evaluation corpus, held-out
confirmation, cloud resource or AI endpoint is read or started. These are trusted
worker methods, not authenticated HTTP operations: application authorization,
independent business-operation approval, Lakebase OAuth/RLS, outbox publication,
source deletion, survivorship and interactive stewardship remain later work.

GitHub publication remains pending because the repository now reports public
while the goal still requires private publication. Local work is authorized.
