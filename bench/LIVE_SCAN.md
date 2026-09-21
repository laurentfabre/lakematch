# Live scan interpretation — 21 September 2026

Later deployment verification is recorded in [REDEPLOYMENT.md](REDEPLOYMENT.md).
Its minimal `reports/redeployment/query-errors.json` receipt shows newer failed
scanner queries referencing nonexistent system-table columns: `duration_ms`,
`spill_to_disk_bytes`, `queued_overflow_count` and `table_size_bytes`. These
specific failures require scanner/query compatibility fixes, not just a warm
warehouse. They do not retroactively establish the cause of the original
HTTP-0 rows, whose underlying errors were absent from that export.

Sources: the preserved `reports/online/findings.json` (scan `fba1702e45e3`) and
the read-only follow-up in
`reports/online-review/workspace-metadata-20260921.json`. The latter was captured
at **2026-09-20 23:34 UTC / 2026-09-21 01:34 Europe/Paris**, explicitly using
`fevm-gdpr2`. It lists metadata only: no SQL, conversation, resource mutation,
or compute startup was performed.

## What the scanner actually established

- **10 checks evaluated: 9 passed and 1 failed.** The evaluated failure is
  **BP-273**, a global-init-script count check. Its expectation also permits
  justified scripts; the receipt does not establish that this alternative was
  evaluated.
- **24 predicates remained unsupported**, including all **7 error-severity
  rows**. Their `pass: false` is paired with `evaluated: false`; this is not a
  confirmed failure. The export retains counts and endpoints, not the original
  API response bodies needed to interpret every setting.
- **12 checks errored**: seven `SqlFailed`/HTTP 0, four HTTP 404, and one HTTP
  400. The seven SQL checks have no SQL error message or statement ID in the
  receipt. Cold startup is the supplied diagnosis; this export alone cannot
  distinguish that from permissions, unavailable tables/columns or another
  execution failure.
- Hundreds of templated or account-level checks were skipped. Nine passes
  establish only the posture covered by those checks.

## Fresh metadata observations

| Resource / rule | Observed state | Interpretation |
|---|---|---|
| Shared starter warehouse, BP-045/053/043 | STOPPED; PRO with serverless enabled; auto-stop 10 minutes; max clusters 1 | Meets the scanned timeout and serverless predicates. |
| Campaign evidence warehouse, BP-045/053/043 | STOPPED; PRO with serverless enabled; auto-stop 10 minutes; max clusters 1 | Meets the same predicates. |
| Warehouse channels, BP-057 | Shared warehouse explicitly CURRENT; campaign warehouse omits `channel` | No explicit PREVIEW setting observed. The omitted value is not treated as measured CURRENT. |
| Global init scripts, BP-273 | Fresh list returns **zero scripts** | The original count-based failure is not reproduced. Historical raw payload is unavailable, so do not assert whether counting or an intervening state change caused the difference. No script was changed or removed. |
| All-purpose clusters, BP-075 | Fresh list returns **zero clusters** | No all-purpose cluster to flag in this inventory. This does not audit every SQL workload's placement. |
| Workspace SCIM, BP-003 | Not established by the exported count | A ServiceProviderConfig capability response alone does not prove an active provisioning connector. The installed rule also marks this check FEVM-exempt. No identity settings were changed. |

## Genie: per-column settings need interpretation

The list-spaces endpoint used by the scanner does not establish the column
settings. The follow-up fetched all five serialized space exports and inspected
`data_sources.tables[].column_configs[].enable_format_assistance` and
`enable_entity_matching`.

| Space ID | Explicitly configured columns | Format assistance true | Entity matching true | Format assistance true, entity matching omitted |
|---|---:|---:|---:|---:|
| `01f1aef1eb4a10bebd44448806b90cbd` | 45 | 45 | 16 | 29 |
| `01f1b02aec3a16c4ab8ed67771f10fe7` | 61 | 61 | 14 | 47 |
| `01f1adfdafeb1a24894f2fab357ab84c` | 0 | 0 | 0 | 0 |
| `01f1adfd1992149995921003d1b57daf` | 0 | 0 | 0 | 0 |
| `01f15f19be521bb68d917b536a23ba47` | 73 | 73 | 28 | 45 |
| **Total** | **179** | **179** | **58** | **121** |

There are **121 columns across three spaces** with format assistance explicitly
enabled and no explicit entity-matching setting. No explicit false setting was
found for those columns. Omitted settings are not proof of effective disabled
behavior. Spaces without column configs do not establish either toggle's
effective defaults.

These are column-level features, not a universal space-level on/off pair. The
installed Genie serialized-space guidance recommends entity matching for stable
low/medium-cardinality string fields that users name directly. Inspect the
types and intended use of the affected columns before proposing edits; blanket
enablement across numeric measures, dates and identifiers is not justified by
this scan. This audit preserved the existing spaces and exported only indices
for affected columns, not source data or saved questions.

## Requested code and housekeeping follow-up

- The app's Delta queue, review and metadata writes already use **insert-only
  MERGE** with immutable keys, as recorded in [the remediation notes](STATIC_SCAN.md).
  The single-writer constraint and pending remote acceptance remain explicit.
- Local `src/lakematch/publication.py` uses SQLite. Its original `INSERT` is
  protected by `BEGIN IMMEDIATE`, a unique batch ID, duplicate/digest checks and
  atomic commit. Replacing the immutable catalog with overwrite semantics would
  lose history. A new concurrency regression test proves four simultaneous
  retries produce **one build, one commit and one shared receipt**. All four
  publication tests pass; the accepted engine source remains unchanged.
- `git check-ignore` confirms `mlruns/`, `data/frozen_models/`,
  `data/remote_models/` and `data/serverless_runs/` are already ignored; none are
  tracked. `python3 tools/scan_source.py` keeps recursive source coverage while
  excluding generated copies. The focused rerun remains **208 files, 0 errors,
  15 warnings and 68 informational findings**. `--no-recursive` at `app/` or
  `src/` would omit the nested implementation this review needs to inspect.

No new campaign experiment, app deployment, Genie conversation or SQL warehouse run
was launched. The incomplete SQL checks still require actual execution evidence;
this metadata review does not mark them passed.
