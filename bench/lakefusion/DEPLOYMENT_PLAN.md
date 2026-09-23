# LF-C slot 5 — dedicated Apps/Lakebase pilot deployment

Declared **2026-09-23**, after the slot-4 runtime payload passed from `6db3086`.
LF-C has consumed 4/8 experiments. This attempt consumes slot 5 even on failure.
Commit this plan, implementation and explicit resource inputs before running.

Hypothesis: the accepted isolated APX payload can start on the selected workspace
with actual service-principal OAuth/TLS, operator-owned migrations and restricted
workflow grants; current-user commands replay identically after app restart and
revocation denies access and retries.

## Scope and bounds

- Explicit profile `fevm-gdpr2`; resource names in
  [deployment-inputs-20260923.json](deployment-inputs-20260923.json).
  LF-DEC-007 authorizes the new dedicated target. The runner refuses existing
  project, app or review schema instead of adopting or overwriting them.
- One project `lakematch-mdm-dev`, branch `production`, default PostgreSQL
  database `databricks_postgres`, control schema `lm_control`. PostgreSQL 17,
  native password login disabled, **0.5–1 CU**, **300-second auto-suspend**.
  Preserve the HR-demo project, old app and old review tables.
- One Medium app, one instance and one Python worker. Separate DAB state and
  resource bindings; deploy stopped, then provision SQL permissions before start.
  No persistent personal credentials, copied secrets or source credentials.
- One previously owned, stopped, tagged serverless 2X-Small warehouse;
  verify owner/name/tag and ≤10-minute auto-stop before using it. A fresh
  `gdpr2_catalog.lakematch_mdm_dev` schema contains three empty Delta review
  tables. Only the new app's SP receives traversal/read grants and MODIFY on
  its own review-label table. The old single-writer store is not shared.
- Overall **2,400 seconds**, at most 2,100 seconds of work, 300 seconds reserved
  for cleanup. Project operations ≤300 seconds, build ≤480, bundle deployment
  ≤300, app readiness ≤600. No additional matching/model/AI runs. One active
  remote experiment. Fail rather than relax unsupported permission contracts.
- SQL uses ≤15-second statement and ≤5-second lock timeouts; operator connects
  sequentially with ≤10-second timeout. App admits at most four connections.
  No corpus/confirmation data. One synthetic master with ERP/CRM crosswalks,
  one task and its immutable command receipt; at most twelve HTTP requests.
- Preserve all 15 frozen Phase A files and seven scanner inputs from slot 4.
  Retain compact run, resource, payload and binding evidence. Secrets and OAuth
  tokens never appear in reports or subprocess command arguments.

## Acceptance and honest limits

1. Actual metadata matches selected project/branch/database, capacities and TLS
   host. The serving role exists and passes unchanged nonowner/no-membership
   constraints. Operator applies six unchanged migrations; serving only checks.
2. Import the already-frozen company contract with its explicit synthetic
   fixture author, approved by the actual operator. This is fixture installation,
   **not proof of two independently authenticated human approvers**.
3. Build the accepted payload, strict-validate the DAB and deploy with isolated
   state. Actual APX startup invokes credential acquisition and SQL readiness.
   Verify a real Apps session, isolated empty review queue and workflow request.
4. A create-task request and exact retry produce one identical receipt. Revoke
   current user's fixture scope: inbox and receipt retry return 403/no-store.
   Restart app; denial persists. Regrant and verify exact original receipt replay.
5. Stop the new app and the warehouse this run started. Retain the selected
   Lakebase project, migration data, stopped app, DAB state and review schema for
   continuation. Lakebase auto-suspends; storage persists and is potentially
   billable. Record observed resource/time attribution; unavailable billing is
   **unreconciled**, never zero. No destructive database/schema/project cleanup.

A failure is terminal evidence for this attempt. Read-only diagnosis may follow;
changed execution needs its own committed follow-up plan and consumes another
slot. A pass qualifies this installation and restart flow only. Hour-long live
token renewal, ingress header isolation, a second authenticated approver,
per-user RLS, database restore, scale/latency, business mutation/publication and
customer installation remain separate gates. LM-007/008/024 stay in progress.

```sh
.venv/bin/python tools/experiment.py --phase LF-C --kind lf-c-deployment \
  --hypothesis 'The isolated APX payload starts on dedicated Lakebase and preserves current grants and immutable receipts across restart' \
  --timeout 2400 --workspace fevm-gdpr2 \
  --config bench/lakefusion/DEPLOYMENT_PLAN.md \
  --artifact bench/lakefusion/deployment-20260923.json \
  --artifact bench/lakefusion/deployment-binding-20260923.json \
  -- .venv/bin/python tools/lakefusion_deployment_run.py
```

The generated payload remains ignored under `data/test-runs/`; its manifest and
committed source provide rebuild instructions. Do not rerun the first-install
runner against retained resources: a later redeployment must explicitly bind to
the recorded IDs and verify migrations/grants without reseeding.
