# LF-C slot 7 — resume the dedicated deployment with preserved diagnostics

Declared **2026-09-23**, after slot 6 from `e296720` created the dedicated
project but failed during bundle deployment. LF-C has consumed **6/8** attempts.
Slot 7 preserves all limits and acceptance requirements of
[DEPLOYMENT_PLAN.md](DEPLOYMENT_PLAN.md). Commit before execution.

Retained project UID: **`ca930294-0763-4eaa-9638-b8be2c4f98b6`**. Endpoint:
`projects/lakematch-mdm-dev/branches/production/endpoints/primary`. Actual
metadata confirms 0.5–1 CU and 300-second suspension. The binding and hashed
payload were built successfully, and strict validation passed. No app or review
schema was created; migrations and SQL warehouse activity never started.

The runner overwrote the original bundle error with the subsequent “app does not
exist” cleanup error. **The original failure cause is unknown.** A subsequent
read-only `bundle plan` succeeds and shows one app create, with exactly the
declared Lakebase/warehouse resources. This is not deployment acceptance.

This run requires the exact retained UID and absence of the new app/review
schema. It reuses the complete recorded payload only after checking every file
hash and the live binding hash. The stopped-app bundle deployment uses explicit
`--auto-approve` for its already-authorized create plan, avoiding an interactive
prompt if one is requested. Both stdout and stderr for every failed CLI command
are retained separately, and cleanup first checks app existence. No permission
or runtime contract is weakened; no resource is deleted or silently adopted.

```sh
.venv/bin/python tools/experiment.py --phase LF-C --kind lf-c-deployment-resume \
  --hypothesis 'The recorded dedicated target and payload can complete Apps deployment with retained diagnostics' \
  --timeout 2400 --workspace fevm-gdpr2 \
  --config bench/lakefusion/DEPLOYMENT_RESUME_PLAN.md \
  --artifact bench/lakefusion/deployment-20260923-resume.json \
  --artifact bench/lakefusion/deployment-binding-20260923-resume.json \
  -- .venv/bin/python tools/lakefusion_deployment_run.py --resume
```

Retain a terminal failure as a consumed slot. Real Apps/Lakebase authentication,
role mapping and restart/revocation must pass before this increment is accepted;
the independent renewal/RLS/second-user/business-flow gates remain open.
