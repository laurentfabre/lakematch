# Prepared LF-C slot 9 — certificate trust and retained-app installation

**Prepared, not authorized or executed.** LF-C is **8/8**. The user must first
amend the LF-C experiment limit; LF-DEC-005 applies only to LF-B. The runner
refuses slot 9 with its default authorized limit of eight.

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

After a user-approved limit amendment is recorded, invoke the bounded runner
with fresh installation report/binding artifacts and
`tools/lakefusion_deployment_run.py --continue-installation
--authorized-phase-limit <approved-LF-C-limit>`. Do not run an ad-hoc command to
bypass the phase limit. Live singleton reporting, Apps OAuth/TLS, migration and
permission readiness, current-user receipt/revocation/restart checks must all
pass. A missing active-instance count remains a qualification failure.

Stop the app and any warehouse started by this attempt; retain the requested
target, schemas, immutable fixture receipts and DAB state. Billing stays
unreconciled until measured. No second-user/RLS/renewal/business-publication
gate closes through this installation alone.
