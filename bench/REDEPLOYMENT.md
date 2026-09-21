# Redeployment audit — 21 September 2026

Profile: **fevm-gdpr2**. The user's request authorized analysis, deployment
verification and pushing the complete repository changes. This follow-up does
not reset benchmark limits or mark the unfinished campaign gates passed.

The root, APX app and Genie bundles were deployed against the existing resources.
Subsequent plans report **skip for all five resources**: two jobs, one pipeline,
one app and one Genie space. No resource replacement was required. The runbook
is [deployment/README.md](../deployment/README.md).

## Fixed deployment gaps

- Completed the scaffold app bundle: existing name, dedicated warehouse binding,
  inline Delta settings, one worker, disabled delegated Genie, stopped lifecycle
  and deletion protection. Bound the existing app instead of creating a duplicate.
- Added the Genie bundle using the actual live export, preserving its ID, title,
  four tables and shared warehouse. Original authoring drafts are preserved.
- Enabled deployment locks; documented the shared state of root's two alternate
  targets. Limited sync to deployment source and isolated app build output.
- Tagged jobs/pipeline and gave every train/cluster fixture run its own volume
  directory. Restarts no longer reuse the previous run's training-report path.
- Added create-if-absent storage/table/grant bootstrap and a **1,067,514-byte**
  checksummed recovery archive. All **45 input files** matched the workspace;
  zero needed uploading. Recovery no longer requires ignored local MLflow folders.
- Made the app build use committed dependencies. APX's regular frontend build
  updated router packages despite a prior frozen install; the deployment wrapper
  uses locked Vite followed by APX packaging and retains source notices.
- Fixed the cloud queue failure found during smoke testing: Statement Execution
  binds integer parameters as BIGINT, while Databricks SQL requires INT for LIMIT.
  `LIMIT CAST(:limit AS INT)` works on both SQLite and the live warehouse.
- Included the earlier insert-only Delta MERGE fixes, immutable metadata/receipt
  handling, local hooks, CODEOWNERS, regression guards, scan interpretations and
  the illustrated nontechnical PDF. The SQLite publication log retains its
  transactional uniqueness protocol, verified with concurrent callers.

## Verification and receipts

| Check | Observed result | Evidence |
|---|---|---|
| Strict validation | Both root targets, app and Genie pass | Bundle plans and deploy logs in `reports/redeployment/` |
| Repeat deployment plans | All five resources unchanged | `*-plan-after.json` |
| Fresh source-only checkout | Public fixture restored; fresh locked app install/build; 13 app tests pass | `clean-checkout.json` |
| Targeted local regression checks | 13 app + 4 publication + 2 guard + 2 recovery tests pass | Local hooks; Python and TypeScript checks also pass |
| Live app | Five HTTP 200 responses; authenticated workspace user; Delta store; empty existing queue/history | `app-smoke.json` |
| Genie NL versus direct SQL | Both return **2,446 links** and one result row | `tests/smoke/ask_genie-result.json` |
| Delta retry probe | Two MERGE replays leave one review; reload preserves receipt; changed metadata rejected; INT limit works | `tests/smoke/delta_review-result.json` |
| Final owned workspace state | App/warehouse STOPPED, pipeline IDLE, no active campaign jobs or probe tables; Genie export matches | `final-workspace.json` |
| Source-only static scan | **0 errors, 19 warnings, 76 info across 225 files** | `reports/redeployment/source-scan/` |

The two earlier app smoke attempts are retained. The first deployed successfully
but exposed the CLI's empty JSON output; the runner now reads the deployment ID
from the Apps API. The second exposed the BIGINT LIMIT bug. The corrected final
run passed frontend/session/queue/history/statistics, then confirmed the app and
owned warehouse STOPPED. The smoke did not seed or modify real review labels.

The additional Delta probe passed its data assertions and dropped all three
disposable tables. Its first warehouse stop waiter timed out; that receipt stays
marked `cleanup_failed`. A separate stop was issued and final state is recorded
in `reports/redeployment/final-workspace.json`; do not interpret the original
cleanup error as a failed retry assertion or erase it from the evidence.

Static warnings are retained without suppression. They include false positives
on the transactional SQLite INSERT and regression fixture, shallow MLflow logging
heuristics, absent serving-endpoint blocks (there is no model-serving endpoint),
and checks against preserved Genie authoring drafts. The deployed export already
has sorted joins and paired format/entity matching on its two state columns.
The optional thumbnail remains unset. CODEOWNERS alone does not enforce GitHub
branch protection; repository hooks remain the local commit gate.

Recent live scan queries also used unavailable system-table columns. The minimal
`query-errors.json` retains those errors plus the app's LIMIT failure. Warming
the warehouse does not fix those query/schema compatibility errors; the older
scan's HTTP-0 rows still lack enough detail to establish their original cause.

## Scope and remaining limits

This proves same-workspace deployment and fresh-checkout input/app recovery.
It is not a destructive disaster-recovery rehearsal. Existing catalog/metastore,
identity and managed-storage provisioning remain prerequisites. The runbook
explains fresh-resource creation, state recovery and warehouse-ID overrides.
Labels, arbitrary UC data, secrets and historical MLflow artifacts need their
normal storage backups; Git cannot reconstruct user decisions.

No new frozen inference, training, million-record or benchmark sweep was run.
The previously accepted engine and sealed benchmark evidence are unchanged.
The cloud app smoke does not prove the full remote 20-review/retraining loop.
One standalone Genie question does not prove all reference questions or delegated
app access. ZR-3 scale, ZR-6 Photon/billing, complete ZR-7 feedback, delegated
ZR-8 and classic-only ZR-9 limitations remain in `goal.md`.

The [11-page PDF](../reports/lakematch-explained/LakeMatch-Explained.pdf) describes
the tested `910a418` campaign snapshot. Its diagrams, figures, screenshots and
editable source are included; this audit records the subsequent deployment work.
