# LF-C slot 16 — workspace-qualified proxy identity

Declared **2026-09-28**, LF-C **15/32**. Slot 15 passes real session and isolated
queue requests, then rejects the first workflow POST with 401. The runtime and
restricted database readiness pass. No workflow receipt or revocation ran.

Hypothesis: the platform uses the numeric `user-id@workspace-id` proxy identity
illustrated by the public [Databricks app-template change](https://github.com/databricks/app-templates/pull/214),
which the mastering parser previously rejected. The actual rejected header was
not captured. Add support only for the exact injected workspace; do not accept
email identities or arbitrary realms, and do not add grants to make a check pass.

- A numeric qualified ID maps to the existing `databricks:workspace:user`
  principal only when the workspace suffix matches exactly. Existing plain IDs
  stay compatible. Duplicate/empty/malformed headers remain unauthorized.
- Local app-boundary tests prove the two forms resolve to the same principal,
  and reject other workspaces, emails, whitespace, separators and ambiguous IDs.
  Fixed rejection classifications go to logs without header values or tokens.
  Managed hooks run app and fresh runtime integration regression before remote
  execution. Initial boundary-only result: **29 passed**.
- Build a fresh hashed payload from committed source; retain all original
  installation/fixture, frozen/scanner and prior evidence. Verify unused workflow
  tables and revision-1 access before any requests. Use direct SNAPSHOT deployment,
  exact deployment-ID checks and uploaded/snapshot hash comparison.
- Repeat the unchanged eight-request functional flow from
  [slot 15](DEPLOYMENT_FUNCTIONAL_PLAN.md): create/exact retry, revoke/read-write
  denial, restart/continued denial, regrant/original receipt, one task/command.
  Missing instance telemetry stays unqualified and prevents an overall pass;
  observed non-singleton counts or larger compute stop the run.

Keep all [startup bounds](DEPLOYMENT_STARTUP_PLAN.md): 2,400 seconds overall,
2,100 work, one active experiment, the same Medium standard app/one worker/four
runtime connections, Lakebase 0.5–1 CU/300-second suspension, and the owned
2X-Small serverless warehouse. Reserve 1,350 seconds before each app start.
Stop owned compute and retain data. Never reseed or silently regrant in cleanup.
Slot 16 is consumed regardless of outcome; broader authorization, RLS, renewal,
business application and operational qualification remain separate gates.

```sh
.venv/bin/python tools/experiment.py \
  --phase LF-C --kind lf-c-identity \
  --hypothesis 'Strictly workspace-matched numeric proxy identities permit the retained workflow receipt and revocation flow without changing grants' \
  --timeout 2400 --workspace fevm-gdpr2 \
  --config bench/lakefusion/DEPLOYMENT_IDENTITY_PLAN.md \
  --artifact bench/lakefusion/startup-identity-inputs-20260928.json \
  --artifact bench/lakefusion/startup-identity-20260928.json \
  -- .venv/bin/python tools/lakefusion_startup_run.py \
       --inputs bench/lakefusion/startup-identity-inputs-20260928.json
```
