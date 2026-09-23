# LF-C slot 9 — certificate trust and retained-app installation

**Authorized, not yet executed.** LF-C is **8/32** under
[LF-DEC-008](../../spec/lakefusion/EXECUTION_DECISIONS.md), implementing Laurent's
2026-09-23 instruction “Increase the cap substantially”. This attempt consumes
slot 9 even on failure. Commit this amendment and plan before running. The
runner requires the amended authorized limit explicitly; its default remains eight.

The next bounded action is concrete: rebuild the isolated APX payload with the
same hash-pinned Certifi CA bundle used by the existing app dependencies, update
the already-owned stopped app, install the six unchanged migrations and narrow
grants, then execute the original live workflow/revocation/restart checks.
The [original plan](DEPLOYMENT_PLAN.md) supplies the unchanged 2,400-second,
0.5–1 CU, Medium/singleton, SQL, fixture, preservation and cleanup bounds.

Retain the exact project UID `ca930294-0763-4eaa-9638-b8be2c4f98b6` and app
`lakematch-mdm-dev`, whose service principal and resource list must match the
[slot-8 report](deployment-20260923-singleton.json). Refuse changed resources,
running compute or existing control/review schemas. Use independent DAB state
and a fresh build/output path. The original source/payload remains historical.

Read-only diagnosis found that local `sslrootcert=system` cannot validate the
certificate. Explicit `sslrootcert=certifi.where()` with **`verify-full`** succeeds
using TLS 1.3. It also confirmed the app role is a nonowner candidate with no
elevated flags or memberships, and `lm_control` is absent. This is operator
diagnosis, not live app service-principal authentication or deployment acceptance.
The prepared fix retains certificate and hostname verification everywhere.

Invoke the bounded runner below with fresh installation report/binding artifacts.
Do not run an ad-hoc command to bypass the phase limit. Live singleton reporting, Apps OAuth/TLS, migration and
permission readiness, current-user receipt/revocation/restart checks must all
pass. A missing active-instance count remains a qualification failure.

Stop the app and any warehouse started by this attempt; retain the requested
target, schemas, immutable fixture receipts and DAB state. Billing stays
unreconciled until measured. No second-user/RLS/renewal/business-publication
gate closes through this installation alone.

```sh
.venv/bin/python tools/experiment.py \
  --phase LF-C --kind lf-c-deployment-installation \
  --hypothesis 'The corrected CA trust permits installation and live workflow acceptance on the retained dedicated app and Lakebase target' \
  --timeout 2400 --workspace fevm-gdpr2 \
  --config bench/lakefusion/DEPLOYMENT_INSTALLATION_PLAN.md \
  --artifact bench/lakefusion/deployment-20260923-installation.json \
  --artifact bench/lakefusion/deployment-binding-20260923-installation.json \
  -- .venv/bin/python tools/lakefusion_deployment_run.py \
       --continue-installation --authorized-phase-limit 32
```
