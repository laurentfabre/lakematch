# LF-C slot 1 — transactional stewardship worker

Declared 2026-09-22 after LF-B source `70d4494`. LF-B remains complete for its
declared foundations at 12/12 experiments. LF-C has consumed 0/8; the first
bounded acceptance attempt below consumes slot 1, including a failure. Focused
development tests and normal hooks do not replace this acceptance record.

Hypothesis: a PostgreSQL worker can maintain one current lease holder, prevent
stale proposals, require independent approval and atomically record immutable
receipts/decisions/outbox events. Original receipts survive lost acknowledgements
and restart, and pre-commit process death leaves no partial command.

Implement and commit the [workflow contract](../../spec/lakefusion/WORKFLOW.md),
additive migration 0005, worker, tests and runner before executing the experiment.
Retain earlier migrations, frozen contracts, old label receipt behavior and the
four scanner report edits. Use no corpus tuning or held-out confirmation data.

Bounds:

- One local experiment; 600-second outer timeout. Root test subprocess ≤180
  seconds; app tests ≤120 seconds. No remote workspace, AI or cloud calls.
- Sequential private temporary PostgreSQL instances; TCP disabled, fsync on,
  maximum 12 configured connections and four concurrent test clients. Each is
  stopped and removed by its owner. Child-process crash tests target only their
  own subprocess. Never connect to a caller-provided DSN or pre-existing server.
- Synthetic fixtures only: two companies per workflow case, at most seven tasks
  in the pagination fixture, bounded evidence and fixed declared scenarios.
- Production worker limits: 32 entities, 900-second leases, 100-row pages,
  32 KiB evidence, 64 KiB requests, 5-second lock / 15-second statement timeouts.
- Record parent peak RSS and highest individual child peak RSS, rejecting either
  above 4 GiB. This is an observed-process bound, not aggregate memory accounting.
- Persist source/migration/plan hashes, exact test commands and JUnit summaries,
  compact restart/retry lifecycle receipts, wall time and owned cleanup evidence.
  Random UUIDs exercise allocation; no method selection or fitted randomness.

Required checks: portable validation; same-key and competing concurrent claims;
lease expiry, lock-wait expiry, token fencing and renewal replay; proposal and
approval transaction rollback; independent approval with one outbox event;
durable changed-company conflict; replay after later state changes/domain
retirement; lost acknowledgement; real child-process death; actual PostgreSQL
restart; immutable SQL rows/transitions; populated version-zero upgrade; UTC
receipts; context isolation; bounded and query-bound pagination. Run all existing
PostgreSQL suites and affected portable mastering/registry/publication checks,
plus the existing APX app tests for label/receipt compatibility.

Pass only if every required test succeeds without skips, the lifecycle survives
restart with exact receipts and unchanged identities, all 15 frozen Phase A
files and four scanner inputs retain their hashes, and owned cleanup completes.
One failed predicate fails the attempt; retain the failure and declare any
follow-up against the remaining LF-C allowance.

Example fresh acceptance command (run after the implementation/plan commit):

```sh
.venv/bin/python tools/experiment.py --phase LF-C --kind lf-c-workflow \
  --hypothesis 'Leases and immutable approval receipts survive concurrency, failure and restart' \
  --timeout 600 --config bench/lakefusion/WORKFLOW_PLAN.md \
  --artifact bench/lakefusion/workflow-20260922.json \
  --artifact bench/lakefusion/workflow-tests-20260922.xml \
  --artifact bench/lakefusion/workflow-app-tests-20260922.xml \
  -- .venv/bin/python tools/lakefusion_workflow_run.py \
  --output bench/lakefusion/workflow-20260922.json \
  --tests-output bench/lakefusion/workflow-tests-20260922.xml \
  --app-tests-output bench/lakefusion/workflow-app-tests-20260922.xml
```

This attempt can accept the internal worker foundation. LF-C and LM-007 stay
open while Lakebase data-plane/OAuth/grants and authenticated application
integration are pending. Role authorization, business preview/apply, publication
delivery/reconciliation, live UI and the broader two-source pilot remain later
Phase C gates. No existing quality, scale or latency result is broadened.
