# LF-B iterations 6–7 — immutable field provenance

Declared 2026-09-22 against `7ec600d`, after 5/8 LF-B slots. Each invocation of
the bounded experiment runner consumes one slot, including a failure. Slot 6 is
the local acceptance run; slot 7 is reserved for one remote Delta integration.
The eighth slot remains available under the existing phase cap.

Hypothesis: golden records, field explanations, source crosswalks and pinned
definitions can be committed as one immutable snapshot, preserving an earlier
revision's explanation after source updates, tombstones and overrides.
Use the contract in [LINEAGE.md](../../spec/lakefusion/LINEAGE.md).

Local: at most 300 seconds overall and 180 seconds for pytest. Verify complete
field/source/decision links, checksum and projection integrity, independent
identity/master revisions, order-independent snapshots, strict bounds, stale
head/source/version refusal, historical read after restart, exact old-batch retry,
concurrent writers and process death. Preserve existing publisher and mastering
regressions. Use only owned temporary SQLite/Postgres storage and synthetic
fixtures; 4 GiB observed main Python RSS ceiling, not aggregate memory.

Remote: one ephemeral serverless job on the already selected `fevm-gdpr2`,
client 4, no AI calls, no evaluation corpus. Use a fresh owned notebook/source
directory and Delta publication namespace under `gdpr2_catalog.lakematch_20260919`.
Do not redeploy or alter the existing demo bundle or tables. Maximum two complete
publications (six companies each), one deliberately interrupted partial table
write and committed-batch retries. At most 16 owned Delta tables including the
catalog; no permanent job or new warehouse. Job/task timeout 900/720 seconds;
outer runner 1,200 seconds, including at most 180 seconds cancellation/cleanup.
Poll in intervals below 60 seconds. Cancel only the submitted run on timeout.

Read both publications through fresh publisher instances, prove old source values
and override provenance remain intact, compare portable/Delta hashes and retain
table versions/counts, run/task IDs, timing, source hashes and terminal status.
Drop only tables with this run's exact owned prefix and delete its workspace
directory after proof. Missing billing remains unreconciled, never zero cost.
Outbox, app authorization, CDC and entity UI remain separate gates.
