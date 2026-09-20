# APX arbitration app — 2026-09-20

APX 0.3.8 is the selected stack. Laurent corrected the installed skill's legacy
classification: “It's not legacy.” That classification no longer blocks UI work.
The original upstream metadata and prerequisite size receipt remain unchanged.

The isolated app now implements uncertainty/LLM-unsure ordering, merge-impact
tie breaks, keyboard match/no-match/unsure, mandatory reasons, server-assigned
reviewer/time, immutable model provenance, retry-safe writes, history, queue and
quarantine statistics, available human/LLM agreement, and evaluation metrics over
model versions. Local SQLite and the prepared remote Delta adapter share these
contracts. Unknown metrics display as unavailable. App dependencies remain
outside the Apache-2.0 engine.

## Measured local acceptance

- Browser run `20260920T105503Z-app-browser-217ea8`: 20 HTTP reviews, one exercised
  through keyboard controls; retries return the original review; provenance,
  statistics/history, hidden Genie and mobile layout pass; zero page errors.
- Normal CLI feedback run `20260920T105553Z-app-feedback-2ab14d` consumes all 19
  resolved labels and excludes one unsure review. Recorded training digest:
  `e4a308dbeb02d9bb5448a824a487e899c85e7fa647ffb019c9b95557c81b7075`.
  It differs from the original eight-label baseline digest. Feedback model:
  `runs:/56dfba9b75ce4db7967f9eb2535b362e/model`.
- Restart run `20260920T105714Z-app-restart-81f874`: an actual APX process stop/start
  preserves every review and the exact training snapshot.
- The fixture is new synthetic data: baseline, review and validation records are
  disjoint. Both model evaluations use the same eight validation pairs. These
  small capability results do not change any benchmark-quality claim.
- Initial final-build checks (`20260920T105826Z-app-local-checks-bffb8d`) passed six
  regression checks, Python/TypeScript checks and a 143,106-byte largest build
  file. Subsequent local checks also cover the prepared provisioning wait and
  deployment-authentication guards. The [final structured audit](../experiments/app-acceptance-20260920.json) records 11 passing tests, both type checkers, the final build size, license inclusion and checksummed evidence.

The first browser attempt could not locate Chromium. The next uncovered SQLite
numeric affinity in metadata. The third asserted history before the asynchronous
fetch returned. Each failed receipt remains in the run ledger. The fixed complete
browser run passes. APX 0.3.8 requires commands from the app directory (or an
absolute path); FastAPI 0.128.0 is pinned for compatible OpenAPI introspection.

## Remote acceptance is incomplete

The four remote attempts are retained:

| Iteration | Experiment | Finding |
|---|---|---|
| 5 | `20260920T105900Z-app-remote-47e95f` | CLI rejects a positional name alongside `--json`; nothing created. |
| 6 | `20260920T105954Z-app-remote-426746` | Explicit default identity scope rejected; nothing created. |
| 7 | `20260920T110137Z-app-remote-1adbbb` | Manual instance count configuration is unavailable; nothing created. |
| 8 | `20260920T110232Z-app-remote-d1963b` | App created asynchronously; immediate read lacked the service-principal ID. Cleanup could not stop initial STARTING state. |

The later independent [cleanup receipt](../experiments/app-resource-cleanup-20260920.json)
confirms the app completed provisioning and is **STOPPED**, its principal exists,
the owned warehouse is **STOPPED**, and the pipeline is **IDLE**. The app has no
active deployment. No new Delta tables, remote labels or remote training were
created by these app attempts. Unrelated apps/compute were untouched. The original
iteration-8 failure and cleanup error are not rewritten.

App: `lakematch-review-20260919` (`d124e6f3-45aa-4693-86ee-b34898aac9d8`).
Owned warehouse: `ec3b6df6c1cabcd4`. Only the platform's default identity scopes
are present. The app requests no optional OAuth scopes or delegated token.
Automatic approval review rejected an earlier proposed Genie scope while Genie
was disabled; that proposal never executed, and the safer review-only request
was accepted. Actual delegated Genie remains ZR-8 work.

## Prepared next step — requires a cap extension

ZR-7 has exhausted its eight iterations. No ninth remote run is authorized.
The prepared runner waits up to 300 seconds for both the service-principal ID
and a terminal provisioning state. Cleanup waits through STARTING and only
issues stop when supported. Offline tests reproduce the observed lifecycle race.
The existing stopped app will be reused; it will not be recreated.

One proposed ninth iteration keeps the same 24-pair/20-review fixture, app code,
SQL warehouse, selected profile, no optional scopes, and one worker. Work stops
at 1,800 seconds, with explicit cleanup reserved inside a 2,700-second outer
limit. It would deploy, check Delta writes/readback and app restart, export the
labels, then stop app/warehouse. No scale rerun, budget increase or other phase
extension is included. [Runner](../app/acceptance/remote.py),
[lifecycle fix](../app/acceptance/lifecycle.py), [plan](APP_PLAN.md).

The Delta adapter assumes one serialized writer, not a distributed lease.
Snapshots/statistics fail explicitly beyond 10,000 rows. Optional Lakebase is
not enabled. ZR-7's read-only verifier correctly remains nonzero until complete
remote acceptance exists. The engine's four passing phase verifiers remain green.
