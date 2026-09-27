# LF-C slot 10 — retained installation and separate compute startup

Declared **2026-09-28**, following the user instruction “Go” to complete the
first live Apps/Lakebase workflow acceptance. LF-C is **9/32** under LF-DEC-008.
This attempt consumes slot 10 even on failure. Commit implementation, this plan
and [explicit inputs](startup-inputs-20260928.json) before execution.

Hypothesis: separately starting app compute with its declared readiness
allowance permits the unchanged, hash-verified payload to deploy and execute
the live task/retry/revocation/restart flow against the retained installation.
Slot 9's 120-second local `bundle run` timeout included compute startup and
expired before source deployment. Its evidence remains immutable.

## Retained state and acceptance

- Use only the selected `fevm-gdpr2` workspace and dedicated `lakematch-mdm-dev`
  resources. Match project UID `ca930294-0763-4eaa-9638-b8be2c4f98b6`, the recorded
  app service principal/resources, and exact endpoint/host/database bindings.
  Refuse a running app/warehouse, a pre-existing app source deployment or another
  active campaign job. Keep the independent DAB state from the original plan.
- Verify all nine retained payload hashes and the pinned installation report,
  binding and cleanup receipts; copy only recorded payload files to a fresh
  output directory. Payload source remains `8320d42`; only the harness changes.
  Verify all 15 frozen inputs and seven user-owned scanner inputs.
- In a **read-only PostgreSQL transaction**, compare the six migration hashes,
  approved frozen domain and synthetic author/operator attribution, one master,
  ERP/CRM crosswalks, immutable identity/access receipts and revision-1 policy.
  Refuse elevated/owning service roles, altered schema grants or prior workflow
  use. Never rerun bootstrap, migrations, grant installation or fixture seeding.
  Read the three retained Delta tables and their exact direct app grants; require
  empty tables before proceeding. No changes to old app/review or HR-demo data.
- Strict-validate and deploy the copied bundle while stopped. Call
  `apps start --no-wait` and poll compute readiness for up to **600 seconds**.
  Then `bundle run workflow --no-wait` submits source deployment on ready compute,
  followed by up to **600 seconds** of application readiness checks. Retain
  command diagnostics, including partial output on local timeouts.
- Require deployment success, app `RUNNING`, compute `ACTIVE` and an observed
  `compute_status.active_instances == 1` before HTTP checks and again after
  restart. A missing instance count remains a failed qualification.
- Verify a real user session and empty review queue; create one task and replay
  the same receipt. Revoke the operator's fixture grants and require 403/no-store
  on inbox and receipt retry. Restart, require continued denial, restore the
  recorded grants and replay the original receipt. Finally read back exactly
  one task/command and match the durable receipt/hash to the HTTP receipt.

## Unchanged envelope and cleanup

One active remote experiment; **2,400 seconds overall**, at most **2,100 seconds
of work**. The child stops cleanup by 2,370 seconds, leaving outer process-group
cleanup time. One Medium app, platform instance defaults with observed singleton
required, one worker and at most four runtime database connections. Lakebase
stays **0.5–1 CU with 300-second auto-suspension**. Use only the owned serverless
2X-Small warehouse with at most 10-minute auto-stop.

Operator PostgreSQL connections are sequential, with 10-second connection,
15-second statement and 5-second lock timeouts, verified TLS and the pinned
Certifi CA bundle. Delta reads use 15-second statement waiting with cancellation,
one row and 1 KiB response limits. HTTP requests use at most 40 seconds each;
the declared flow has eight requests and is bounded by twelve. No matching,
AI inference, corpus or confirmation materialization occurs.

Every app start requires at least **1,350 seconds remaining before the cleanup
deadline**, accounting for the platform's 20-minute restriction on stopping an
app stuck in `STARTING`. On failure, use unused time inside the same overall
envelope to reconcile that state. Stop the owned warehouse and app; retain the
project, installed schemas, fixture, audit receipts and DAB state. Never repair
failed revocation checks by silently granting access during cleanup. Record any
uncompleted cleanup explicitly. Billing remains unreconciled, not zero.

Six private PostgreSQL development checks cover retained receipt preservation
across restart and rejection of operator/master/migration/role/revocation drift.
These checks do not establish remote authentication or feature acceptance.
Managed commit hooks run the affected PostgreSQL regression suite as well.

```sh
.venv/bin/python tools/experiment.py \
  --phase LF-C --kind lf-c-startup \
  --hypothesis 'Separate compute startup permits the retained payload to pass live workflow retry and revocation checks without reseeding' \
  --timeout 2400 --workspace fevm-gdpr2 \
  --config bench/lakefusion/DEPLOYMENT_STARTUP_PLAN.md \
  --artifact bench/lakefusion/startup-inputs-20260928.json \
  --artifact bench/lakefusion/startup-20260928.json \
  -- .venv/bin/python tools/lakefusion_startup_run.py \
       --inputs bench/lakefusion/startup-inputs-20260928.json
```

A pass covers this first deployment, current-user workflow and restart only.
Independent human approval, ingress isolation, per-user RLS, hour-long renewal,
business apply/publication, restore, scale and customer installation remain open.
LM-007/008/024 stay in progress. Failures count; changed execution needs a fresh
committed follow-up plan and evidence paths.
