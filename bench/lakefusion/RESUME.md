# Lakematch resume checkpoint

Saved **2026-10-01**. Repository state checked locally on this date; remote state
below was last verified **2026-09-28 Europe/Paris**, not refreshed for this note.
This is a navigation aid. [The goal](../../goal_lakefusion.md),
[phase evidence](PHASE_C.md) and [backlog](../../spec/research/lakefusion/backlog.csv)
remain the authorities.

## Where we stopped

The first live current-user workflow milestone **passes**: authenticated session,
empty review queue, task creation, exact retry, revoked read/write denial,
continued denial after app restart, and original-receipt replay after regrant.
All eight HTTP checks passed with statuses **200, 200, 200, 200, 403, 403, 403, 200**.

The overall experiment is still **failed**, solely because Databricks omitted
`compute_status.active_instances` before and after restart. Functional success
does not close deployment qualification or the wider pilot. Do not infer an
observed singleton from absent telemetry or the standard-app default.

- Latest implementation/evidence published to public GitHub `main`:
  **`be36ed284d38b2d9a3455f87c59d924bcba017d0`** in `laurentfabre/lakematch`.
- Tested implementation: **`a6e074a43a5fe531f7c414b602b1d73553133c56`**.
- Accepted functional run: **`20260927T233626Z-lf-c-identity-05ae8f`**, 321.234 seconds.
- Checks before deployment: **54 app tests**, plus **133 isolated runtime checks
  on each of Python 3.11 and 3.12**. Thirteen deployment-harness tests also passed.
- LF-A **8/8**, LF-B **12/12**, LF-C **16/32**: **16 LF-C attempts remain**.
  The cap is not the blocker. Original campaign limits are unchanged.
- LM-007, LM-008 and LM-024 remain in progress. Phases D–F remain open.

Evidence:

- [Run manifest](../../experiments/20260927T233626Z-lf-c-identity-05ae8f/manifest.json)
- [Live report](startup-identity-20260928.json)
- [Independent read-only reconciliation](startup-identity-verification-20260928.json)
- [Exact inputs](startup-identity-inputs-20260928.json)
- [Declared run plan](DEPLOYMENT_IDENTITY_PLAN.md)

## Retained state — never reset it to rerun acceptance

The installed fixture now contains **one task and one durable command**. The
original grants were restored at **access revision 3**, with immutable access
events at revisions **1/2/3**. There are **zero business operations, decisions or
outbox entries**; business apply/publication has not been demonstrated.

- Master: `d400ec99-003a-4b26-aa0a-de7d37d8052c`.
- Task: `312e0437-362b-48a4-90ed-ba970340c5de`.
- Command: `8e22c272-2cc4-45a0-bd19-4bab1074cffc`.
- Receipt SHA-256: `6abf4d97246e952788389a9197c8c71857c8ffea2f370ccfb5a6e8366aa4ec0a`.
- Idempotency key: `deployment-task-v1`.

**Do not rerun the first-use plans for slots 10–16.**
[The retained-state verifier](../../tools/workflow_retained.py) intentionally
rejects nonempty workflow tables and access revision other than 1. A further
live experiment needs a new committed continuation that pins and verifies these
existing receipts and revision 3. Never reseed, drop, erase receipts or silently
regrant during cleanup to get a passing result.

Last verified app and warehouse state: **STOPPED**. Lakebase schemas/data and
DAB state were retained; maximum **1 CU**, idle suspension **300 seconds**.
Billing remains **unreconciled**, not zero.

## Selected target and standing decisions

- User-selected CLI profile: **`fevm-gdpr2`**. Pass it explicitly; do not ask for
  selection again or switch workspaces. Load the current Databricks core and
  matching product skills before remote operations.
- Workspace: `https://fevm-gdpr2.cloud.databricks.com`, ID `7474658055368199`.
- Dedicated app and Lakebase project: **`lakematch-mdm-dev`**.
- Lakebase branch `production`, database `databricks_postgres`, schema `lm_control`.
- Review tables: `gdpr2_catalog.lakematch_mdm_dev`.
- Owned serverless warehouse: `ec3b6df6c1cabcd4`.
- Exact endpoint, database resource, host and domain bindings:
  [deployment binding](deployment-binding-20260923-installation.json).
- Preserve unrelated `hr-demo-20260914`, `lakematch-review-20260919` and old data.
- Keep **APX 0.3.8, React and FastAPI**. Deliver a customer Solution Accelerator
  and SA demo kit, using synthetic ERP + CRM and legal-company masters.
- Use AI via Unity Gateway under the approved protocol v0.1; this milestone did
  not exercise AI or qualify automatic business mutations.
- Commit and push completed work to the **public** GitHub repository through
  managed hooks. Use GitHub account **`laurentfabre`**; the default account may
  differ. Never print or persist tokens.
- User waived FEVM spend/quota discovery; finite resource/time limits and cleanup
  remain. No native goal tracker, Lighthouse sidecars or subagents are in use.

## Deployment lessons already fixed

1. Start app compute separately from source deployment; cold start previously
   exhausted the source-deployment command timeout.
2. Explicitly inject `LAKEBASE_ENDPOINT` using `valueFrom: postgres`. Accept only
   equivalent spellings of the bound HTTPS workspace origin.
3. CLI 1.18.0 `bundle run` reused a stale environment override from retained DAB
   state. The runner keeps DAB validation/resource deployment/sync, verifies all
   uploaded files, then uses named `apps deploy --source-code-path ... --mode
   SNAPSHOT --no-wait` without command/environment overrides. Pin the returned
   deployment ID and verify snapshot hashes, including after restart.
4. Accept numeric `user-id@workspace-id` proxy identities only when the workspace
   suffix exactly matches the injected workspace. Canonical principals stay
   `databricks:workspace:user`; no grants were broadened. Logs contain fixed
   rejection classifications, not header values.

The last diagnostic explicitly collected functional evidence despite missing
instance telemetry, while retaining an overall qualification failure. It still
rejected observed non-singleton counts or larger compute. Preserve that
distinction in later reports.

## Resume from here

1. Read this note, the goal's §6/§11, the final Phase C checkpoint and verification
   receipt. Recheck local changes and current workspace state before mutations.
2. Resolve instance-count observability without treating missing data as proof.
   Explicit instance controls were rejected by this workspace. Browser inspection
   was unavailable because the managed Chrome profile was already in use; no
   browser was stopped or reconfigured.
3. Prepare a continuation that preserves the used fixture and audit history
   before another live run. Keep one remote experiment, finite deadlines, startup
   cleanup reserve and owned-resource cleanup; record all attempts in the ledger.
4. Qualify a real second authenticated approver and ingress isolation. Per-user
   RLS, hour-long credential renewal, business apply/publication, recovery/scale
   and customer installation remain separate gates. Implement eligible business
   apply/publication work under the existing package dependencies.

Do not claim the governed MDM pilot, independent human approvals, RLS, business
publication or customer installation are complete from this eight-request test.

## Local files to preserve

The working tree has user-owned scanner changes under `reports/findings.*`,
`reports/online/findings.*`, and untracked scan directories dated **20260922**
and **20260928**. Leave them untouched and unstaged. The seven original scanner
input hashes are in [runtime inputs](runtime-inputs-20260923.json); all matched
after the final push. Preserve all 15 files listed in the
[Phase A freeze](../../spec/lakefusion/frozen/phase-a-v0.1.json), plus failed run
manifests and historical payloads. Generated artifacts remain ignored.

To resume execution: `$goal ./goal_lakefusion.md`.
