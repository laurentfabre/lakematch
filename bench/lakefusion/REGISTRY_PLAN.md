# LF-B iteration 2 — durable registry and execution binding

Date: 2026-09-22. Prerequisite: Phase A freeze and candidate comparison at
`e4cf355`. LF-B currently has one experiment receipt; this run consumes slot 2
whether it passes or fails. No LF-A or old ZR envelope is reopened.

**Hypothesis:** PostgreSQL can preserve immutable domain/mapping/execution
versions, independent approval and optimistic revisions across concurrency and
restart, and a registry-bound job exactly replays the chosen candidate method
without changing the old v1 engine contract.

Run focused typed-contract, policy, retrieval, execution, existing v1 config and
source-hygiene tests plus explicit local PostgreSQL integration. The optional
driver is locked in `requirements-postgres.lock`. Start only a private temporary
PostgreSQL instance with TCP disabled, fsync on, at most 12 connections, 5-second
lock and 15-second SQL-statement limits; stop it and remove its owned directory.
Use synthetic internal actors, not claims of authenticated app users. Test:

- Checksummed additive migration, repeat apply, changed-file/downgrade refusal
  and atomic rejection of unattributed legacy approvals.
- Draft isolation, immutable definitions, exact-payload retry, stale revisions,
  concurrent submit/approve with one winner, and atomic version/audit rollback.
- Mapping/domain digest binding, source drift, bounded preview with one branch
  quarantined, current approved dependencies, retirement and audit pagination.
- Persistent approvals after actual PostgreSQL restart; code/hash mismatch refusal.
- Explicit v1 feature-row projection while old engine configs remain unchanged.

Then seed/approve the selected ERP/CRM company definitions and an execution
version that pins **identifier + normalized name**, exactly the previous
cheapest-passing selection. No weights, matching methods, thresholds or data
corruptions change. Replay the existing **validation** inputs (4,000 per source)
against the retained raw candidate rows and report identical semantic hashes,
3,800/4,000 recovered positives and the original 200 combined-error misses.
This is an execution-binding regression, not another model-selection sweep.

Keep 50 candidates per ERP, 2m retained pairs, 20m postings, 120 seconds for this
retrieval call and 20,000 input rows per source. Measure process peak RSS against
4 GiB; outer experiment maximum **300 seconds**, unit/integration test subprocess
maximum 120 seconds. Only development integration fixtures and the already
exposed validation partition are read; no confirmation data is generated.

Record code/config/migration/lock/input hashes, version/approval manifests,
candidate semantic hash, assertion counts, failure details, timing and cleanup.
No Databricks API, warehouse, app, Lakebase instance or AI service is started or
called. Remote Lakebase OAuth/RLS, authenticated registry APIs, publication,
persistent master IDs and auto-merge quality remain separate gates.
