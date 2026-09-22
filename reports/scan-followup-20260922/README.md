# Follow-up: recurring static and live scan findings

Reviewed the refreshed reports against source commit `d09b46c` on 2026-09-22.
**No new source warning locations and no new review-store defect were found.**
The [summary](summary.json) records input hashes, exact counts and dispositions;
the user's four refreshed report files were not edited.

| Scan | Files | Errors | Warnings | Info |
|---|---:|---:|---:|---:|
| Refreshed raw static report | 10,006 | 0 | 333 | 1,492 |
| Fresh [source-only scan](source-scan/findings.md) | 294 | 0 | 21 | 94 |

The source scan has exactly the same warning rule/file locations as the earlier
[triaged scan](../triage-20260922/README.md). It ran through
`python tools/scan_source.py --out reports/scan-followup-20260922/source-scan`.
The [scope manifest](source-scan/scope.json) identifies every input and checksum.
This wrapper excludes ignored/generated trees while retaining nested source;
`--no-recursive` would omit real code. `mlruns/` and all `data/` descendants
already have Git ignore coverage. Of the raw scan's 333 warnings, **294** are
in generated trees and **39** are elsewhere, including historical reports.

The repeated BP-101 description is stale: the latest raw JSON contains **zero
findings of any rule** in `app/src/lakematch_review/backend/store.py`,
`app/acceptance/fixture.py` or `app/acceptance/remote.py`. Current review storage
already uses SQLite unique indexes/`ON CONFLICT DO NOTHING` and Delta immutable-key
`MERGE`; acceptance code calls `enqueue`/`set_metadata`. Those fixes predate this
follow-up. The Delta single-worker limitation still applies. Remaining source
BP-101 warnings have the transaction/constraint and test-fixture dispositions in
the previous triage. No SQL was changed, and unchanged tests were not rerun.

The live report still records **10 evaluated checks: 9 pass, 1 fail**, plus 24
unsupported predicates, seven of which have error severity. Its 12 errors are
**7 `SqlFailed`, 1 HTTP 400 and 4 HTTP 404**. There is no diagnostic establishing
cold start as their cause. Unsupported/error rows remain unevaluated, not passes.
The evaluated failure is BP-273 (global init scripts), which the earlier
read-only metadata triage did not reproduce. This follow-up made no remote calls
and does not claim a new workspace verification.

The Genie builder still explicitly sets `enable_format_assistance` and
`enable_entity_matching`, and sorts `join_specs` by ID. Its thumbnail omission
remains cosmetic. No cosmetic resource change was made.

No campaign experiment, compute startup, deployment or acceptance-gate change
occurred. LF-B remains **8/8**, with calibration and app acceptance pending the
proposed cap extension. Repository publishing still awaits resolution of the
private-repository requirement versus the observed public GitHub visibility.
