# LF-C slot 2 — current-grant APX workflow access

Declared **2026-09-23**, after accepted source `2ae4207`. LF-C has consumed
1/8 experiments. The next bounded acceptance attempt consumes slot 2, including
a failure. Development checks and managed hooks are separate from this record.

Hypothesis: the actual APX routes can bind the platform user ID to server-owned
domain/role/object/field grants, deny revoked users even on exact command retry,
serialize revocation with admitted transactions, and execute the supported
workflow using a nonowner SQL role. No hidden task/operation/history data should
appear through list pagination or generic errors.

Commit the [access contract](../../spec/lakefusion/ACCESS.md), additive migration
0006, API/worker boundary, tests, generated client and runner before execution.
Preserve all 15 frozen Phase A files, earlier migrations, existing label receipts,
all three app dependency files and the five scanner files identified in
[access-inputs-20260923.json](access-inputs-20260923.json).

## Resource envelope

- One local acceptance experiment; outer timeout **900 seconds**. Fresh APX build
  ≤420 seconds; pinned TypeScript/Python checks ≤60 seconds each; root tests
  ≤180; isolated HTTP helper ≤180.
- Helper steps use offline caches, each ≤60 seconds; its tests ≤90. Python 3.12
  app environment comes from frozen `app/uv.lock`, plus `requirements-postgres.lock`
  and PyYAML 6.0.3. APX stays 0.3.8 and FastAPI 0.128.0.
- Sequential private temporary PostgreSQL instances, TCP disabled, fsync on,
  maximum 12 configured connections, at most four concurrent fixture clients.
  Stop/remove only owned databases and temporary HTTP runtimes.
- Small synthetic fixtures only: two companies per access case, up to four tasks
  per scoped-page case, fixed allow/deny/revocation cases. No evaluation corpus,
  sealed confirmation, live user credentials, cloud or workspace calls.
- API bodies ≤64 KiB, grants ≤16, combined object scope ≤1024, pages ≤100;
  JSON structure/node limits apply. No workload comparison or quality tuning.
- Record parent/highest-child peak RSS and reject either above 4 GiB. This is
  per-process observation, not an aggregate limit.

## Required evidence and pass conditions

Run all portable mastering/compatibility tests and every owned PostgreSQL suite.
Build a fresh APX wheel, verify installed import paths/source hash, and execute
the existing app tests plus HTTP/Postgres integration tests from that wheel.
Capture JUnit, versions, build/type result, source/migration hashes, experiment
duration, an audited grant/revocation/regrant lifecycle and cleanup.

Required scenarios: five-role matrix; stable workspace/user principal; local
identity refusal; request-supplied identity/grants rejected; wrong domain/object
and incomplete field access denied; SQL list filtering before pagination;
cursor user/policy binding; independent approval; all lease mutations denied
after downgrade; revoked reads/history/exact retries denied without side effects;
concurrent revocation ordering; receipt policy attribution; empty-grant and
immutable audit behavior; real restart; populated schema-5 upgrade; nonowner-role
operation and forbidden SQL; bounded JSON, error hygiene and no-store responses.

Every required check must pass without skips. Frozen/scanner/dependency hashes
must remain unchanged and owned resources must be cleaned. A failed predicate
fails the run and remains in the append-only ledger; declare any follow-up within
the remaining LF-C allowance before executing it.

```sh
.venv/bin/python tools/experiment.py --phase LF-C --kind lf-c-access \
  --hypothesis 'Current grants protect APX workflow reads, commands and retries across revocation and restart' \
  --timeout 900 --config bench/lakefusion/ACCESS_PLAN.md \
  --artifact bench/lakefusion/access-20260923.json \
  --artifact bench/lakefusion/access-tests-20260923.xml \
  --artifact bench/lakefusion/access-http-20260923.json \
  --artifact bench/lakefusion/access-http-tests-20260923.xml \
  -- .venv/bin/python tools/lakefusion_access_run.py \
  --output bench/lakefusion/access-20260923.json \
  --tests-output bench/lakefusion/access-tests-20260923.xml \
  --http-report bench/lakefusion/access-http-20260923.json \
  --http-tests bench/lakefusion/access-http-tests-20260923.xml
```

A passing run accepts this local API/policy boundary, not the whole LM-008 or
Phase C. The platform ingress is simulated; actual Apps authentication/isolation,
Lakebase OAuth/roles/RLS, deployment packaging and field-projected entity/search/
graph/cache paths remain unproved. Business preview/apply, outbox delivery and
publication reconciliation are unchanged later gates. LF-A remains 8/8 and
LF-B 12/12; no historical limit or confirmation result is reset.
