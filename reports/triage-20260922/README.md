# Static and live scan triage — 22 September 2026

**No review-store idempotency defect was reproduced.** The refreshed raw JSON has
no findings in `app/src/lakematch_review/backend/store.py` or either acceptance
script. Those line references describe older code. The change from this review
is a hardened, documented source-only scan workflow, backed by regression tests.
The original static and live reports are preserved byte-for-byte in
[`input-reports.tar.gz`](input-reports.tar.gz), with hashes in
[input provenance](input-provenance.json). Only trailing blank lines in the two
readable Markdown reports were trimmed to satisfy the existing commit hook;
their JSON files are unchanged.

## Reproducible source scan

```bash
python tools/scan_source.py
# Or choose a new, unused evidence directory:
python tools/scan_source.py --out reports/source-scan/<new-run>
```

The wrapper copies current Git-tracked and untracked source into a temporary
repository. It includes nested engine/app code, migrations, tests, tools, all
three bundles, examples and dependency files. It excludes ignored files even
when they were accidentally force-added to Git, symlinks, generated datasets,
model copies and historical evidence. Each report records the copied paths,
their SHA-256 hashes and the source commit. The default output is timestamped;
an existing output directory is refused to protect prior evidence.

`.gitignore` already covered `mlruns/` and all `data/` descendants, including
`test-runs/`, `frozen_models/`, `remote_models/` and `serverless_runs/`. No files
from those trees are tracked. Adding more redundant Git patterns would not fix
the raw scanner's traversal. The installed scanner's help exposes no ignore-file
option; the snapshot makes scope explicit. `--no-recursive` is inappropriate
for this repository because real code is nested below `app/src/` and `src/`.

| Scan | Files scanned | Errors | Warnings | Info |
|---|---:|---:|---:|---:|
| User's [raw static scan](../findings.md) | 9,904 | 0 | 331 | 1,475 |
| [Initial source snapshot](../source-scan-20260922/findings.md) | 250 | 0 | 21 | 85 |
| [Final source snapshot](source-scan/findings.md), with examples/dependencies | 261 | 0 | 21 | 85 |

The final snapshot copied 284 files; the scanner's own file filters evaluated
261. Its scope is source hygiene, not a scan of every historical document. No
findings were suppressed. Offline bundle validation is disabled, so these
results do not replace the existing [redeployment evidence](../../bench/REDEPLOYMENT.md).

The raw JSON contains **294 warnings in `data/` and `mlruns/`, leaving 37**,
rather than the reported 55. Of those 37, 17 are in historical reports and one
is in the old benchmark harness. The fresh source scan also sees two PostgreSQL
registry/test findings from work completed after the raw scan. Raw scan times
are 2026-09-21 22:06 UTC, which is 22 September in Paris.

## Disposition of all 21 current warnings

| Rule / rows | Disposition and evidence |
|---|---|
| BP-101 / 4 | SQLite publication, PostgreSQL registry and two test files; see retry analysis below. The test hits contain intentional regression fixtures or controlled database setup. |
| BP-128 / 7 | The resumed MLflow runs call `tracking.evaluate_pairs`; that helper logs the dataset, runs `mlflow.models.evaluate` and writes the evaluation contract. The grep only looks for direct `mlflow.log_*` calls in each caller's file. Existing model/tracking evidence remains applicable. |
| BP-381, BP-542 / 6 | Each of the three bundles lacks model-serving endpoints. Current engine execution is batch and the app uses Delta/SQL; adding unused endpoints would not improve it. Online model serving remains future roadmap work and must be qualified when implemented. |
| BP-549, BP-555 / 2 | Genie builder false positives: actual fields are `enable_format_assistance` and `enable_entity_matching`; `join_specs` is sorted by ID. The saved artifact is version 2, has sorted joins and one consolidated instruction block. |
| BP-551 / 1 | Genuine cosmetic omission: the existing Genie space has no thumbnail. It remains open and has no bearing on matching correctness. |
| BP-131 / 1 | The bounded historical serverless canary uses a per-user experiment path. It is not the customer deployment template; generalized customer packaging remains LM-024 work. |

### Retry analysis

- **Review storage:** `SQLiteStore.insert_once` uses `ON CONFLICT DO NOTHING`
  with unique indexes; operations use `BEGIN IMMEDIATE`. `DeltaStore.insert_once`
  already uses immutable-key `MERGE`. The returned receipt is read back so a
  retry preserves the original timestamp. Delta's existing **single-writer /
  one-app-worker limitation still applies**; this is not a distributed uniqueness
  guarantee or completion of concurrent stewardship.
- **Acceptance scripts:** both call `enqueue` and `set_metadata`; neither has
  the alleged direct append. They also refuse to seed over existing batches or
  labels rather than replacing previous evidence.
- **Local publication:** a unique `batch_id`, `BEGIN IMMEDIATE`, digest checks
  and a prior-commit lookup serialize the whole build/commit. Retrying a batch
  returns the original receipt; changed input is rejected. Replacing this SQLite
  INSERT with a Delta MERGE would be incorrect for this backend.
- **PostgreSQL registry:** primary/unique constraints, transaction-scoped locks,
  immutable-version checks and atomic audit insertion implement exact retries.
  Migration history has a primary key and is read under its migration lock before
  insertion. The existing [18 PostgreSQL integration cases](../../bench/lakefusion/registry-tests-20260922.xml)
  cover concurrent submission, approval, rollback, migration drift and restart.
  They were not rerun for this scanner-only change.

Fresh verification passed **21 tests, zero failures/errors/skips**:

- [Eight source/publication tests](source-and-publication-tests.xml): generated
  copies and ignored tracked files excluded, new nested source included, prior
  reports protected, regression guards, concurrent duplicate publishers,
  digest conflicts and process death before commit.
- [Thirteen app tests](app-tests.xml): concurrent review retries, duplicate
  queue/metadata writes, lost acknowledgements, restart persistence and app
  lifecycle/authentication boundaries. One third-party deprecation warning remains.

Commands were `.venv/bin/python -m pytest -q tests/test_source_scan.py
tests/test_source_hygiene.py tests/test_publication.py` from the root and
`.venv/bin/python -m pytest -q tests` from `app/`, each with the linked JUnit
output path. Local commit hooks now run the scan-scope tests when the wrapper or
its checks change. Existing SQL regression guards remain in force.

## Live report interpretation

The [raw live report](../online/findings.md) records 10 evaluated checks (9 pass,
1 fail), **24 unsupported predicates** (seven with error severity), and 12 check
errors. Unevaluated rows are not confirmed workspace failures. The 12 errors are
**seven `SqlFailed`, one HTTP 400 and four HTTP 404**, not twelve cold-start SQL
errors. The report contains no SQL diagnostic proving cold start as the cause.
A retry would require suitable live SQL diagnostics and supported endpoints.

A fresh [read-only metadata receipt](workspace-metadata.json) on the explicitly
selected `fevm-gdpr2` profile found:

| Area | Observation / limit |
|---|---|
| Warehouse posture | Both warehouses are `PRO` with serverless enabled, stopped, auto-stop 10 minutes and maximum one cluster. Neither is Classic. |
| Channel | Starter warehouse explicitly uses CURRENT. The campaign warehouse omits the channel field, so its effective channel is not established by this response. |
| BP-273 evaluated failure | The raw scanner says one global init script. Direct CLI enumeration returns `[]`; direct REST returns `{}`, with zero scripts. The failure is not reproduced and no script needs removal. Earlier metadata also recorded zero scripts. Treat the scanner's count as suspect, not proof of a global init script. |
| BP-075 | No all-purpose clusters are present. Query execution/history posture was not inferred from an empty cluster inventory. |
| Lakematch Genie | Space `01f1b55eb48a1c0bae6f117fbdbc064e`: both format-assisted columns explicitly enable entity matching. |
| Other Genie spaces | Three spaces have 29, 45 and 47 format-assisted columns without explicit entity matching. Omitted settings and column types require owner interpretation; this is not proof of bad answers. Those spaces are outside Lakematch's managed resources. |
| SCIM | `ServiceProviderConfig` exposes supported API capabilities, not whether an identity-provider provisioning connection is active. This remains unverified. |
| Tags | Warehouse tags do not establish the scanner's general environment/owner/cost-center policy. Current metadata is retained; no shared workspace policy was changed. |

The audit used warehouse/cluster/Genie list and get calls, plus read-only REST
GETs for global init scripts and SCIM metadata. It started no compute, executed
no SQL, changed no resources and exported no conversations or table rows. A
blanket live re-scan against stopped warehouses was unnecessary for these facts.

## Campaign state

This is LM-024 maintenance. LF-B remains **2/8 experiments**, with LM-002/003
complete and LM-004 persistent identities next. No feature gate, auto-merge
quality claim or customer release qualification was changed. The
[machine-readable summary](summary.json) ties raw/final counts and test results
to checksummed evidence; the final scan scope records exact reviewed source.
